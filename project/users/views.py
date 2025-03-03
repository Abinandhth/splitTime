from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, logout as authlogout, login as authlogin
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from .models import Pdf,Settings
from datetime import timedelta

def main(request):
    return render(request, 'main.html')

def login(request):
    error_message = None
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)

        if user:
            authlogin(request, user)
            return redirect('home')
        else:
            error_message = 'Invalid credentials'

    return render(request, 'login.html', {'error_message': error_message})

def logout(request):
    authlogout(request)
    return redirect('main')

@login_required(login_url='/login/')
def home(request):
    # Ensure user settings exist
    user_settings, created = Settings.objects.get_or_create(
        user_settings=request.user,
    )

    if request.method == 'POST':
        # File upload handling
        uploaded_file = request.FILES.get('document')
        pdf_title = request.POST.get('pdfTitle')
        deadline = request.POST.get('deadline')

        if uploaded_file:
            Pdf.objects.create(
                pdf_file=uploaded_file,
                user=request.user,
                title=pdf_title,
                deadline=deadline
            )
        else :
             # Update settings only if values are provided
            min_val = request.POST.get('min')
            if min_val and min_val.strip():
                user_settings.min = int(min_val)

            max_val = request.POST.get('max')
            if max_val and max_val.strip():
                user_settings.max = int(max_val)

            duration_val = request.POST.get('duration')
            if duration_val and duration_val.strip():
                if ':' in duration_val:
                    hours, minutes = map(int, duration_val.split(':'))
                    user_settings.duration = timedelta(hours=hours, minutes=minutes)
                else:
                    user_settings.duration = timedelta(minutes=int(duration_val))

            from_time = request.POST.get('from')
            if from_time and from_time.strip():
                user_settings.from_time = from_time

            to_time = request.POST.get('to')
            if to_time and to_time.strip():
                user_settings.to_time = to_time

            # Save updated settings
            user_settings.save()

            return redirect('home')
       

    # Retrieve PDFs uploaded by the user
    pdfs = Pdf.objects.filter(user=request.user)

    return render(request, 'home.html', {
        'pdfs': pdfs,
        'from_time': user_settings.from_time.strftime('%H:%M'),
        'to_time': user_settings.to_time.strftime('%H:%M'),
        'duration': user_settings.duration.total_seconds() // 60,  # Convert timedelta to minutes
    })



def signup(request):
    error_message = None
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')

        try:
            User.objects.create_user(username=username, password=password, email=email)
            return redirect('login')  # Redirect to login after signup
        except Exception as e:
            error_message = "Account Already Exits"

    return render(request, 'signup.html', {'error_message': error_message})

def pdf_delete(request,pk):
    if request.method == 'POST':
        pdf= Pdf.objects.get(pk=pk)
        pdf.delete()
    return redirect('home')