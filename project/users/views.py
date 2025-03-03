from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, logout as authlogout, login as authlogin
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from .models import Pdf,Settings
from datetime import datetime, date, timedelta
from pdf.models import TimeSlots,sections
import fitz
from django.core.files.base import ContentFile

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

            pdf_obj = Pdf.objects.create(
                pdf_file=uploaded_file,
                user=request.user,
                title=pdf_title,
                deadline=deadline
            )

            selected_timeslots_json = request.POST.get('selected_timeslots', '')
            import json
            try:
                selected_timeslots = json.loads(selected_timeslots_json)
                    
                # Parse the deadline string to a date object
                deadline_date = datetime.strptime(deadline, '%Y-%m-%d').date()
                today = datetime.now().date()
                    
                # Create TimeSlots for each day from today to deadline
                current_date = today
                while current_date < deadline_date:
                    for slot in selected_timeslots:
                        start_time = datetime.strptime(slot['start_time'], '%H:%M').time()
                        end_time = datetime.strptime(slot['end_time'], '%H:%M').time()
                        
                        # For today, skip time slots that are already past
                        if current_date == today and start_time < datetime.now().time():
                            continue
                                
                    # Create the TimeSlots entry
                        TimeSlots.objects.create(
                            tpdf=pdf_obj,
                            date=current_date,
                            start_time=start_time,
                            end_time=end_time
                        )
                        
                        # Move to the next day
                    current_date += timedelta(days=1)

                total_time = TimeSlots.objects.filter(tpdf__title=pdf_title).count()
                print(total_time)

                split_and_store_pdf(pdf_obj,total_time)  

                assign_sections_to_timeslots(pdf_obj)

            except json.JSONDecodeError:
                print("Error decoding selected time slots JSON")
            except ValueError as e:
                print(f"Error parsing date or time: {e}")

                    

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

    schedules = []
    time_slots = TimeSlots.objects.all().order_by('date','start_time')

    dates_dict = {}
    for slot in time_slots:
        date_str = slot.date.strftime('%d/%m/%Y')
        if date_str not in dates_dict:
            dates_dict[date_str]= []
        
        section_url = slot.section.section_file.url if slot.section and slot.section.section_file else None


        slot_str = f"{slot.start_time.strftime('%I:%M%p')}-{slot.end_time.strftime('%I:%M%p')}"
        slot_entry = {'time': slot_str,'section_url':section_url}
        dates_dict[date_str].append(slot_entry)

    dates_list = [{'date': date, 'slots': slots}
            for date, slots in sorted(dates_dict.items())
    ]

    schedules.append({'dates':dates_list})

    return render(request, 'home.html', {
        'pdfs': pdfs,
        'from_time': user_settings.from_time.strftime('%H:%M'),
        'to_time': user_settings.to_time.strftime('%H:%M'),
        'duration': user_settings.duration.total_seconds() // 60, 
        'schedules':schedules
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


def split_and_store_pdf(pdf_obj,num_splits):
    pdf_path = pdf_obj.pdf_file.path
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    if num_splits == 0 or num_splits > total_pages:
        print("error:invalid no of splits")
        return
    pages_per_split = total_pages // num_splits

    for i in range(num_splits):
        start_page = i * pages_per_split
        end_page = start_page + pages_per_split

        if i == num_splits -1:
            end_page = total_pages

        new_pdf = fitz.open()
        for page_num in range(start_page,end_page):
            new_pdf.insert_pdf(doc,from_page=page_num,to_page=page_num)

        pdf_bytes = new_pdf.write()
        new_pdf.close()

        section_obj = sections(pdf=pdf_obj)

        section_obj.section_file.save(
            f"section_{i+1}.pdf",
            ContentFile(pdf_bytes)
        )

        section_obj.save()

def assign_sections_to_timeslots(pdf_obj):
    sections_list = list(sections.objects.filter(pdf=pdf_obj).order_by('id'))

    timeslots_list = list(TimeSlots.objects.filter(section__isnull=True,tpdf=pdf_obj).order_by('date','start_time'))

    for timeslot,section in zip(timeslots_list,sections_list):
        timeslot.section = section
        timeslot.save()
    print("succes assigned")       