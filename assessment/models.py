from django.db import models
from django.utils import timezone
import uuid

class Assessment(models.Model):
    domain = models.CharField(max_length=100)
    test_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    number_of_questions = models.IntegerField()
    duration_minutes = models.IntegerField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    cutoff_score = models.IntegerField()
    sheet_gid = models.CharField(max_length=50, null=True, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def result_sheet_link(self):
        from django.conf import settings
        base_url = getattr(settings, 'APPS_SCRIPT_SHEET_URL', '#')
        if base_url != '#' and self.sheet_gid:
            # Append gid to open specific tab
            return f"{base_url}#gid={self.sheet_gid}"
        return base_url

    @property
    def computed_sheet_name(self):
        local_start_time = timezone.localtime(self.start_time)
        start_time_str = local_start_time.strftime('%Y_%m_%d_%H_%M')
        domain_clean = self.domain.replace(' ', '_')
        return f"{domain_clean}_{start_time_str}"

    @property
    def current_status(self):


        now = timezone.now()
        if now > self.end_time:
            return "Expired"
        if not self.is_active:
             return "Inactive"
        if now < self.start_time:
             return "Scheduled"
        return "Active"

    def __str__(self):
        return f"{self.domain} - {self.test_code}"

class Attempt(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Qualified', 'Qualified'),
        ('Rejected', 'Rejected')
    ]

    candidate_email = models.EmailField()
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True) # Null if not submitted yet
    questions_dump = models.TextField(default='[]')
    score = models.IntegerField(default=0)
    percentage = models.FloatField(default=0.0)
    warning_count = models.IntegerField(default=0)
    result_status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='Pending'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        unique_together = ('candidate_email', 'assessment')

    def __str__(self):
        return f"{self.candidate_email} - {self.assessment.test_code}"

class AuditLog(models.Model):
    user = models.CharField(max_length=150)  # Using CharField to store username or email
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user} - {self.action} at {self.timestamp}"

class CandidateResponse(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE)
    question_id = models.CharField(max_length=50)
    selected_option = models.CharField(max_length=10)
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('attempt', 'question_id')

    def __str__(self):
        return f"{self.attempt.candidate_email} - Q{self.question_id}: {self.selected_option}"

