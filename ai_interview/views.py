from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import InterviewPractice, PersonalityAnalysis
from .forms import QuestionForm, AnswerForm
from transformers import pipeline

# Initialize AI models
question_generator = pipeline("text2text-generation", model="google/flan-t5-large")
suggested_answer_generator = pipeline("text2text-generation", model="google/flan-t5-large")
answer_evaluator = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")

# 🔹 Home Page
def home(request):
    return render(request, 'home.html')

# 🔹 Register View
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

# 🔹 Login View
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

# 🔹 Logout View
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")

# 🔹 Interview Practice Dashboard

@login_required
def index(request):
    question_form = QuestionForm()
    answer_form = AnswerForm()
    practice = None
    feedback = None
    suggested_answer = None

    if request.method == "POST":
        if "generate_question" in request.POST or "try_another_question" in request.POST:
            question_form = QuestionForm(request.POST)
            if question_form.is_valid():
                domain = question_form.cleaned_data['domain']
                job_description = question_form.cleaned_data['job_description']

                prompt = f"Generate a unique interview question for a {domain} role. Job requirements: {job_description}"
                question_output = question_generator(prompt, max_length=50, num_return_sequences=1, do_sample=True, temperature=0.9)[0]['generated_text']

                practice = InterviewPractice.objects.create(
                    user=request.user,
                    domain=domain,
                    job_description=job_description,
                    question=question_output.strip()
                )

        elif "submit_answer" in request.POST:
            practice_id = request.POST.get("practice_id")
            practice = InterviewPractice.objects.get(id=practice_id)
            answer_form = AnswerForm(request.POST, instance=practice)

            if answer_form.is_valid():
                practice.user_answer = answer_form.cleaned_data["user_answer"]

                evaluation_result = answer_evaluator(practice.user_answer)[0]
                label = evaluation_result['label']
                score = evaluation_result['score']

                feedback = "✅ Excellent response!" if label == "POSITIVE" and score > 0.85 else \
                           "⚠️ Good answer, but you could improve it." if label == "POSITIVE" else \
                           "❌ Needs improvement. Try being more specific."

                practice.feedback = feedback
                practice.save()

        elif "get_suggested_answer" in request.POST:
            practice_id = request.POST.get("practice_id")
            practice = InterviewPractice.objects.get(id=practice_id)

            answer_prompt = f"Provide a detailed and structured answer for the interview question: '{practice.question}' based on the job description: {practice.job_description}."
            suggested_answer_output = suggested_answer_generator(
                answer_prompt,
                max_length=500,
                num_return_sequences=1,
                do_sample=True,
                temperature=0.7,
                top_p=0.9
            )[0]['generated_text']

            practice.suggested_answer = suggested_answer_output.strip()
            practice.save()
            suggested_answer = practice.suggested_answer

    return render(request, "index.html", {
        "question_form": question_form,
        "answer_form": answer_form,
        "question": practice.question if practice else None,
        "practice_id": practice.id if practice else None,
        "feedback": feedback,
        "suggested_answer": suggested_answer
    })
@login_required(login_url='/login/')
def summary_view(request):
    user_responses = InterviewPractice.objects.filter(user=request.user).order_by('-id')
    personality = PersonalityAnalysis.objects.filter(user=request.user).first()

    return render(request, "summary.html", {
        "user_responses": user_responses,
        "personality": personality
    })
import random
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import InterviewPractice, PersonalityAnalysis
from transformers import pipeline
import json

# Initialize AI sentiment analysis model
sentiment_analyzer = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")

@login_required
def analyze_personality(request):
    user_responses = InterviewPractice.objects.filter(user=request.user, user_answer__isnull=False)

    if not user_responses.exists():
        return render(request, "personality.html", {"error": "No responses available for analysis."})

    # Initialize personality traits with base scores
    traits = {
        "openness": 50,
        "conscientiousness": 50,
        "extraversion": 50,
        "agreeableness": 50,
        "neuroticism": 50
    }

    # AI-based personality adjustments
    for response in user_responses:
        answer = response.user_answer.lower()
        sentiment = sentiment_analyzer(answer)[0]  # Sentiment analysis result

        if "creative" in answer or "curious" in answer:
            traits["openness"] += random.randint(5, 10)
        if "organized" in answer or "detail" in answer:
            traits["conscientiousness"] += random.randint(5, 10)
        if "team" in answer or "lead" in answer:
            traits["extraversion"] += random.randint(5, 10)
        if "helpful" in answer or "cooperate" in answer:
            traits["agreeableness"] += random.randint(5, 10)
        if sentiment["label"] == "NEGATIVE":
            traits["neuroticism"] += random.randint(5, 15)

    # Normalize scores (0-100)
    for key in traits:
        traits[key] = min(traits[key], 100)

    # Store or update personality analysis in database
    personality, created = PersonalityAnalysis.objects.update_or_create(
        user=request.user,
        defaults=traits,
    )

    return render(request, "personality.html", {"traits": json.dumps(traits)})
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import InterviewPractice

@login_required
def clear_history(request):
    if request.method == "POST":
        InterviewPractice.objects.filter(user=request.user).delete()
        messages.success(request, "Your interview history has been cleared.")
        return redirect("summary")
