from .models import Assessment, Attempt, CandidateResponse
from .utils import GoogleSheetsAPI
from django.utils import timezone
from django.db import transaction
import random
import json

class AssessmentService:

    @staticmethod
    def get_candidate_data(email):
        """
        Iterates through all domains to find the candidate.
        Returns (candidate_data, domain) if found, else (None, None).
        """
        try:
            domains = GoogleSheetsAPI.get_domains()
            if not domains:
                return None, None
                
            for domain in domains:
                # Assuming domains list is string names
                candidates = GoogleSheetsAPI.get_candidates(domain)
                if not candidates:
                    continue
                    
                for candidate in candidates:
                    # Check both email and phone fields as API seems to have them swapped or inconsistent
                    candidate_email = str(candidate.get('email', '')).strip().lower()
                    candidate_phone_field = str(candidate.get('phone', '')).strip().lower()
                    
                    target_email = str(email).strip().lower()
                    
                    # Logic to find email in either field
                    found = False
                    if candidate_email == target_email:
                        found = True
                    elif candidate_phone_field == target_email: 
                        # If found in phone field, trust it (data issue in sheet)
                        found = True
                        
                    if found:
                        if str(candidate.get('status')).lower() == 'approved':
                            return candidate, domain
            return None, None
        except Exception as e:
            print(f"Error fetching candidate data: {str(e)}")
            return None, None

    @staticmethod
    def get_active_test_for_domain(domain):
        """Returns the active test for a given domain."""
        now = timezone.now()
        return Assessment.objects.filter(
            domain=domain, 
            is_active=True,
            start_time__lte=now,
            end_time__gte=now
        ).first()


    @staticmethod
    def initialize_test(request, email, domain):
        """
        Initializes the test session.
        Returns (success, message_or_object)
        """
        # 1. Get Active Assessment
        assessment = AssessmentService.get_active_test_for_domain(domain)
        if not assessment:
            return False, "No active test found for this domain right now."

        # 2. Check Previous Attempt (Resume or Block)
        existing_attempt = Attempt.objects.filter(candidate_email=email, assessment=assessment).first()
        
        if existing_attempt:
            if existing_attempt.submitted_at:
                return False, "You have already attempted this test."
            
            # Resume logic
            try:
                questions = json.loads(existing_attempt.questions_dump) if existing_attempt.questions_dump else []
            except:
                questions = []

            if not questions:
                # Fallback for old attempts without dump 
                # (Ideally shouldn't finish here if migration done properly but for safety)
                return False, "Cannot resume test. Question data missing."
            
            request.session['test_session'] = {
                'attempt_id': existing_attempt.id,
                'questions': questions,
                'start_time': str(existing_attempt.start_time), 
                'duration_minutes': assessment.duration_minutes
            }
            return True, existing_attempt

        # 3. Create Attempt Record
        try:
            with transaction.atomic():
                attempt = Attempt.objects.create(
                    candidate_email=email,
                    assessment=assessment,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    result_status='Pending'
                )
        except Exception as e:
            return False, f"Database Error: {str(e)}"

        # 4. Fetch Questions
        all_questions = GoogleSheetsAPI.get_questions(domain)
        if not all_questions:
            attempt.delete() 
            return False, "Error fetching questions from database."

        # 5. Randomize & Select N questions
        num_questions = assessment.number_of_questions
        final_sample_size = min(num_questions, len(all_questions))
        selected_questions = random.sample(all_questions, final_sample_size)

        # 5b. Save questions to attempt (for resumption)
        attempt.questions_dump = json.dumps(selected_questions, default=str)
        attempt.save()

        # 6. Store in Session
        request.session['test_session'] = {
            'attempt_id': attempt.id,
            'questions': selected_questions,
            'start_time': str(attempt.start_time), 
            'duration_minutes': assessment.duration_minutes
        }
        
        return True, attempt

    @staticmethod
    def submit_test(request, submitted_answers):
        """
        Evaluates the test and saves result.
        submitted_answers: dict {question_id: selected_option}
        """
        sess = request.session.get('test_session')
        if not sess:
            return False, "Session expired or invalid."

        questions = sess.get('questions', [])
        attempt_id = sess.get('attempt_id')
        
        try:
            attempt = Attempt.objects.get(id=attempt_id)
        except Attempt.DoesNotExist:
            return False, "Attempt record not found."

        if attempt.submitted_at:
             return False, "Test already submitted."

        # Evaluation
        score_obtained = 0.0
        total_possible_score = 0.0
        
        for q in questions:
            q_id = str(q.get('question_id'))
            marks = float(q.get('marks', 1))
            negative = float(q.get('negative_marks', 0))
            correct_opt = str(q.get('correct_option')).strip().upper()
            
            total_possible_score += marks
            
            user_selected = submitted_answers.get(q_id)
            
            if user_selected:
                user_selected = str(user_selected).strip().upper()
                if user_selected == correct_opt:
                    score_obtained += marks
                else:
                    score_obtained -= negative

        final_score = max(0, int(score_obtained)) # Ensure integer score per model
        percentage = (final_score / total_possible_score * 100) if total_possible_score > 0 else 0.0

        attempt.score = final_score
        attempt.percentage = round(percentage, 2)
        attempt.submitted_at = timezone.now()
        attempt.result_status = 'Qualified' if final_score >= attempt.assessment.cutoff_score else 'Rejected'
        attempt.save()

        # Send to Google Sheet
        candidate_data, _ = AssessmentService.get_candidate_data(attempt.candidate_email)

        # Construct result sheet name format: domain_start_date_time
        # Use assessment.start_time, formatted appropriately
        # Convert to local time for sheet naming consistency
        local_start_time = timezone.localtime(attempt.assessment.start_time)
        start_time_str = local_start_time.strftime('%Y_%m_%d_%H_%M')
        # Sanitize domain name just in case (replace spaces with underscores)
        domain_clean = attempt.assessment.domain.replace(' ', '_')
        result_sheet_name = f"{domain_clean}_{start_time_str}"
        
        payload = {
            'candidate_id': candidate_data.get('candidate_id', 'N/A') if candidate_data else 'N/A',
            'name': candidate_data.get('name', 'Unknown') if candidate_data else 'Unknown',
            'email': attempt.candidate_email,
            'domain': attempt.assessment.domain,
            'test_code': result_sheet_name, # Sending formatted name as test_code for sheet creation
            'score': final_score,
            'total_marks': total_possible_score,
            'percentage': round(percentage, 2),
            'result_status': attempt.result_status
        }
        
        GoogleSheetsAPI.append_result(payload)
        
        if 'test_session' in request.session:
            del request.session['test_session']
        
        return True, attempt

    @staticmethod
    def save_response(attempt_id, question_id, selected_option):
        try:
            attempt = Attempt.objects.get(id=attempt_id)
            CandidateResponse.objects.update_or_create(
                attempt=attempt,
                question_id=question_id,
                defaults={'selected_option': selected_option}
            )
            return True
        except Exception as e:
            return False

    @staticmethod
    def log_warning(attempt_id):
        try:
            attempt = Attempt.objects.get(id=attempt_id)
            attempt.warning_count += 1
            attempt.save()
            return attempt.warning_count
        except Exception as e:
            return 0

    @staticmethod
    def get_existing_responses(attempt_id):
        responses = CandidateResponse.objects.filter(attempt_id=attempt_id)
        return {r.question_id: r.selected_option for r in responses}

