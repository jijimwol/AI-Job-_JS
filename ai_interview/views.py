from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from transformers import pipeline
from .models import InterviewPractice, PersonalityAnalysis

# Initialize AI pipelines
question_generator = pipeline("text2text-generation", model="google/flan-t5-large")
suggested_answer_generator = pipeline("text2text-generation", model="google/flan-t5-large")
answer_evaluator = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")

# Home View
def home(request):
    return render(request, 'home.html')

# Register View
def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("register")

        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()
        messages.success(request, "Registration successful! You can now log in.")
        return redirect("login")

    return render(request, "log_reg.html")

# Login View
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("index")  # Redirect to home page after login
        else:
            messages.error(request, "Invalid credentials.")
            return redirect("login")

    return render(request, "log_reg.html")

# Logout View
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")

# Index View
def index(request):
    return render(request, 'index.html')

# Summary View
@login_required
def summary_view(request):
    """
    Renders the summary page with user's interview responses and personality analysis.
    """
    user_responses = InterviewPractice.objects.filter(user=request.user).order_by('-id')
    
    # Fetch personality analysis if available
    personality = PersonalityAnalysis.objects.filter(user=request.user).first()

    return render(request, "summary.html", {
        "user_responses": user_responses,
        "personality": personality
    })

# Generate Interview Question
@csrf_exempt
def generate_question(request):
    if request.method == 'POST':
        domain = request.POST.get('domain', 'general')
        job_description = request.POST.get('job_description', '')
        new_question = request.POST.get('new_question', 'false').lower() == 'true'

        if not job_description:
            return JsonResponse({'error': 'Job description is required'}, status=400)

        prompt = (f"Generate {'another' if new_question else 'a'} unique domain-specific interview question for a {domain} role. "
                  f"Job requirements: {job_description}")

        try:
            question_output = question_generator(prompt, max_length=50, num_return_sequences=1, do_sample=True, temperature=0.9)[0]['generated_text']

            # Save to DB
            practice = InterviewPractice.objects.create(
                user=request.user,  # ✅ Assign the logged-in user
                domain=domain,
                job_description=job_description,
                question=question_output.strip()
            )

            return JsonResponse({
                'question': question_output.strip(),
                'practice_id': practice.id
            })

        except Exception as e:
            return JsonResponse({'error': f'Error generating question: {str(e)}'}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

# Evaluate User's Answer
@csrf_exempt
def evaluate_answer(request):
    if request.method == 'POST':
        user_answer = request.POST.get('user_answer', '')
        question = request.POST.get('question', '')
        practice_id = request.POST.get('practice_id')

        if not user_answer or not question:
            return JsonResponse({'error': 'Answer and question required'}, status=400)

        try:
            evaluation_result = answer_evaluator(user_answer)[0]
            label = evaluation_result['label']
            score = evaluation_result['score']

            if label == "POSITIVE" and score > 0.85:
                feedback = "✅ Excellent response! You nailed it."
            elif label == "POSITIVE":
                feedback = "⚠️ Good answer, but you could expand with specific examples."
            elif label == "NEGATIVE" and score > 0.7:
                feedback = "❌ Needs improvement. Focus on aligning with the question."
            else:
                feedback = "❓ The answer was too vague. Add details and examples."

            # Update DB
            practice = InterviewPractice.objects.get(id=practice_id)
            practice.user_answer = user_answer
            practice.feedback = feedback
            practice.save()

            return JsonResponse({'feedback': feedback, 'confidence': f"{score:.2f}"})

        except Exception as e:
            return JsonResponse({'error': f'Error evaluating answer: {str(e)}'}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

# Generate Suggested Answer
@csrf_exempt
def get_suggested_answer(request):
    if request.method == 'POST':
        question = request.POST.get('question', '')
        job_description = request.POST.get('job_description', '')
        practice_id = request.POST.get('practice_id')

        if not question or not job_description:
            return JsonResponse({'error': 'Question and job description are required'}, status=400)

        try:
            answer_prompt = (f"Provide a detailed and structured answer for the interview question: '{question}' "
                             f"based on the following job description: {job_description}. Include an introduction, "
                             f"key points, and a conclusion with specific examples.")

            suggested_answer_output = suggested_answer_generator(
                answer_prompt,
                max_length=500,  # Increased length for detailed responses
                num_return_sequences=1,
                do_sample=True,  # Allow variation
                temperature=0.7,  # More balanced creativity
                top_p=0.9  # Better-quality responses
            )[0]['generated_text']

            # Update DB
            practice = InterviewPractice.objects.get(id=practice_id)
            practice.suggested_answer = suggested_answer_output.strip()
            practice.save()

            return JsonResponse({'suggested_answer': suggested_answer_output.strip()})
        except Exception as e:
            return JsonResponse({'error': f'Error generating suggested answer: {str(e)}'}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)
