from django.urls import path
from . import views
urlpatterns=[
    path('', views.login_view, name="login"),
    path('index',views.index,name='index'),
    path('summary/',views.summary_view,name='summary_view'),
    # path('login_reg/',views.login_reg,name='login_reg'),
    path('home/',views.home,name='home'),
    path('generate_question/', views.generate_question, name='generate_question'),
    path('evaluate_answer/', views.evaluate_answer, name='evaluate_answer'),
    path('get_suggested_answer/', views.get_suggested_answer, name='get_suggested_answer'),
    # path(" ", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    # path('personal-analysis/',views.personal_analysis, name='personal_analysis'),  # Suggested Answer
]
