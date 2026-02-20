from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from .models import Assessment, Attempt
from .utils import GoogleSheetsAPI
from .services import AssessmentService
from .forms import CandidateLoginForm, AssessmentCreateForm
import json

def index(request):
    return redirect('candidate_login')

def candidate_login(request):
    if request.method == 'POST':
        form = CandidateLoginForm(request.POST) 
        if form.is_valid():
            email = form.cleaned_data['email']
            candidate, domain = AssessmentService.get_candidate_data(email)
            
            if candidate and domain:
                 request.session['candidate_email'] = email
                 request.session['candidate_domain'] = domain
                 request.session['candidate_name'] = candidate.get('name')
                 return redirect('start_test')
            else:
                 messages.error(request, "Email not found or not approved in any domain.")
    else:
        form = CandidateLoginForm()
        
    return render(request, 'assessment/login.html', {'form': form})

def candidate_logout(request):
    request.session.flush()
    messages.success(request, "Logged out successfully.")
    return redirect('candidate_login')

def start_test(request):
    email = request.session.get('candidate_email')
    domain = request.session.get('candidate_domain')
    
    if not email:
        return redirect('candidate_login')
        
    assessment = AssessmentService.get_active_test_for_domain(domain)
    
    # Check if already attempted
    existing_attempt = None
    if assessment:
         existing_attempt = Attempt.objects.filter(candidate_email=email, assessment=assessment).first()
    
    if existing_attempt:
         if existing_attempt.submitted_at:
             return redirect('result_view', attempt_id=existing_attempt.id)
         # Resume immediately or let them click "Start Test" to resume
         # "Start Test" button triggers initialize_test which handles resumption now.
         pass 

    return render(request, 'assessment/start_test.html', {
        'assessment': assessment, 
        'candidate_name': request.session.get('candidate_name', 'Candidate'),
        'domain': domain
    })

def initialize_test(request):
    """Called when user clicks Start Test button"""
    email = request.session.get('candidate_email')
    domain = request.session.get('candidate_domain')
    
    if not email:
        return redirect('candidate_login')
        
    success, result = AssessmentService.initialize_test(request, email, domain)
    
    if success:
        return redirect('take_test')
    else:
        messages.error(request, str(result))
        return redirect('start_test')

def take_test(request):
    sess = request.session.get('test_session')
    if not sess:
        return redirect('start_test')
        
    questions = sess.get('questions', [])
    attempt_id = sess.get('attempt_id')
    submission_success = False

    # Check for hard time limit
    start_time_str = sess.get('start_time')
    duration_minutes = sess.get('duration_minutes', 60)
    
    # Need to verify if test allowed time window is exceeded
    # But assessment object is not in session. Fetch it?
    # Or rely on start_time + duration.
    # What if end_time < start_time + duration?
    # We should have stored end_time in session or fetch assessment.
    
    # Fetch existing responses to pre-fill
    responses = AssessmentService.get_existing_responses(attempt_id)

    # Fetch assessment to get absolute end time
    try:
        attempt = Attempt.objects.get(id=attempt_id)
        assessment_end_time = attempt.assessment.end_time
    except:
        assessment_end_time = None


    # Add index for template
    questions_display = []
    for i, q in enumerate(questions):
        q_copy = q.copy() # Avoid mutating session content directly (though dicts are refs usually)
        q_copy['index'] = i + 1
        # Pre-select option if saved
        q_id = str(q.get('question_id')) # Ensure string
        if q_id in responses:
            q_copy['selected_option'] = responses[q_id]
        questions_display.append(q_copy)
        
    context = {
        'questions': questions_display,
        'duration': duration_minutes,
        'start_time': start_time_str,
        'end_time': str(assessment_end_time) if assessment_end_time else None
    }
    return render(request, 'assessment/take_test.html', context)


def submit_test(request):
    if request.method == 'POST':
        submitted_answers = {}
        # Expecting naming convention q_{id}
        for key, value in request.POST.items():
            if key.startswith('q_'):
                q_id = key.replace('q_', '') 
                submitted_answers[q_id] = value
                
        success, result = AssessmentService.submit_test(request, submitted_answers)
        
        if success:
            return redirect('result_view', attempt_id=result.id)
        else:
            messages.error(request, str(result))
            return redirect('take_test')
            
    return redirect('take_test')

def result_view(request, attempt_id):
    attempt = get_object_or_404(Attempt, id=attempt_id)
    # Security check: Ensure session email matches 
    if attempt.candidate_email != request.session.get('candidate_email'):
        # Allow admin?
        if not request.user.is_superuser:
            return redirect('candidate_login')
            
    return render(request, 'assessment/result.html', {'attempt': attempt})

def save_answer(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Or handle POST dict if sending form data via fetch
            # Since fetch usually sends JSON, let's use json.loads
            # But let's support both
            if not data and request.POST:
                data = request.POST

            attempt_id = request.session.get('test_session', {}).get('attempt_id')
            if not attempt_id:
                return JsonResponse({'status': 'error', 'message': 'No active session'}, status=400)
            
            question_id = data.get('question_id')
            selected_option = data.get('selected_option')
            
            success = AssessmentService.save_response(attempt_id, question_id, selected_option)
            if success:
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({'status': 'error'}, status=500)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

def log_warning(request):
    if request.method == 'POST':
        attempt_id = request.session.get('test_session', {}).get('attempt_id')
        if not attempt_id:
            return JsonResponse({'status': 'error', 'message': 'No active session'}, status=400)
        
        count = AssessmentService.log_warning(attempt_id)
        return JsonResponse({'status': 'success', 'count': count})
    return JsonResponse({'status': 'error'}, status=405)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    assessments = Assessment.objects.all().order_by('-created_at')
    return render(request, 'assessment/admin_dashboard.html', {'assessments': assessments})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def create_test(request):
    domains = GoogleSheetsAPI.get_domains()
    
    if request.method == 'POST':
        form = AssessmentCreateForm(request.POST, domains=domains) 
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.is_active = True
            
            # Create Google Sheet Tab
            sheet_name = assessment.computed_sheet_name
            result = GoogleSheetsAPI.create_result_sheet(sheet_name)
            
            if result.get('status') == 'success':
                assessment.sheet_gid = str(result.get('gid', ''))
                messages.success(request, f"Assessment and Result Sheet '{sheet_name}' created!")
            else:
                messages.warning(request, f"Assessment created but failed to create sheet: {result.get('message')}")
            
            assessment.save()
            return redirect('admin_dashboard')
    else:
        form = AssessmentCreateForm(domains=domains)
        
    return render(request, 'assessment/create_test.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_test(request, test_id):
    assessment = get_object_or_404(Assessment, id=test_id)
    if request.method == 'POST':
        assessment.delete()
        messages.success(request, "Assessment deleted successfully.")
    return redirect('admin_dashboard')
