from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, logout as authlogout, login as authlogin
from django.contrib.auth.decorators import login_required
from .models import Pdf,Settings
from datetime import datetime, timedelta
from pdf.models import TimeSlots
import fitz
from django.core.files.base import ContentFile
from django.db.models import Q
import os
from io import BytesIO


def main(request):
    return render(request, 'main.html')

def account_guide(request):
    return render(request,'account_guide.html')

def stay_motivated_guide(request):
    return render(request,'stay_motivated_guide.html')

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
    timeslots = TimeSlots.objects.none()
    # Ensure user settings exist
    user_settings, created = Settings.objects.get_or_create(
        user_settings=request.user,
    )

    now = datetime.now()  # Uses your PC's local time
    current_date = now.date()
    current_time = now.time()
    print(current_date)
    print(current_time)

    datetime_before = TimeSlots.objects.filter(time_status=False).filter(
        Q(date__lt=current_date) |  # Past dates
        Q(date=current_date, end_time__lt=current_time)  # Today's past times
    )

    datetime_before.update(time_status=True)# Bulk update instead of looping
    tpdfs = Pdf.objects.filter(user=request.user)


    for pdf in tpdfs:

        time_count = TimeSlots.objects.filter(tpdf=pdf,time_status=False).count()
        print(time_count)

        section_count = TimeSlots.objects.filter(tpdf=pdf,section_status=False).count()
        print(section_count)

        if time_count < section_count and time_count>0:
            timeslots = TimeSlots.objects.filter(tpdf=pdf,section_status=False)
            merged_pdf = merge_pdfs_in_memory(timeslots)
            section_list = list(TimeSlots.objects.filter(tpdf=pdf,time_status=False).order_by('date', 'start_time'))
            split_merged_pdf(merged_pdf,time_count,section_list)
        # elif section_count < time_count:
        #     timeslots = TimeSlots.objects.filter(tpdf=pdf,time_status=False).filter(Q(date__gt=now.date()) | Q(date=now.date(), start_time__gte=now.time())).order_by('date', 'start_time')
        #     merged_pdf = merge_pdfs_in_memory(timeslots)
        #     section_list = list(timeslots)
        #     num_splits = timeslots.count()  # Get the count
        #     if num_splits > 0:  # Ensure it's not zero
        #         split_merged_pdf(merged_pdf, num_splits, section_list)
        #     else:
        #         print("No available TimeSlots with time_status=False to assign split PDFs.")

        


    if request.method == 'POST':
        # File upload handling
        uploaded_file = request.FILES.get('document')
        pdf_title = request.POST.get('pdfTitle')
        deadline = request.POST.get('deadline')
        structured = request.POST.get('is_stretched')

        if uploaded_file:

            pdf_obj = Pdf.objects.create(
                pdf_file=uploaded_file,
                user=request.user,
                title=pdf_title,
                deadline=deadline,
                structured = structured,
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

                total_time = TimeSlots.objects.filter(tpdf=pdf_obj).count()
                print(total_time)

                user_settings = Settings.objects.get(user_settings=request.user)
                min_section = user_settings.min

                pdf_obj.total_noof_timeslots = total_time
                pdf_obj.save()

                if pdf_obj.structured:
                    pdf_path = pdf_obj.pdf_file.path
                    processed_pdf=process_pdf(pdf_path)
                
                split_and_store_pdf(pdf_obj,total_time,min_section,processed_pdf)  

                
            except json.JSONDecodeError:
                print("Error decoding selected time slots JSON")
            except ValueError as e:
                print(f"Error parsing date or time: {e}")

                    

        else :
             # Update settings only if values are provided
            min_val = request.POST.get('min')
            if min_val and min_val.strip():
                user_settings.min = int(min_val)

            # max_val = request.POST.get('max')
            # if max_val and max_val.strip():
            #     user_settings.max = int(max_val)

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

    username = request.user.username.upper() if request.user.is_authenticated else "Guest"

    return render(request, 'home.html', {
        'from_time': user_settings.from_time.strftime('%H:%M'),
        'to_time': user_settings.to_time.strftime('%H:%M'),
        'duration': user_settings.duration.total_seconds() // 60, 
        "username": username
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
    return redirect('sections')


def split_and_store_pdf(pdf_obj,num_splits,min,processed_pdf):
    if pdf_obj.structured:
        # Convert bytes to a PyMuPDF Document
        doc = fitz.open("pdf", processed_pdf)
        total_pages=len(doc)
    else:
        pdf_path = pdf_obj.pdf_file.path
        doc = fitz.open(pdf_path)
        total_pages = len(doc)

    i=1
    revision = 0
    if num_splits > total_pages:
        print("error:invalid no of splits")
        num_splits = (num_splits//2)
        revision =(2**i)-1

    while total_pages//num_splits < min:
        num_splits = (num_splits//2)
        i+=1
        revision = (2**i)-1
    pages_per_split = total_pages // num_splits

    pdf_obj.revision = revision
    pdf_obj.save()

    section_list = list(TimeSlots.objects.filter(tpdf=pdf_obj).order_by('date', 'start_time'))

    for i, section in enumerate(section_list):
        # Determine which split this section should belong to (cycling through first num_splits)
        split_index = i % num_splits  

        start_page = split_index * pages_per_split
        end_page = start_page + pages_per_split

        if split_index == num_splits - 1:
            end_page = total_pages  # Ensure last split gets remaining pages

        # Create a new PDF for this section
        new_pdf = fitz.open()
        for page_num in range(start_page, end_page):
            new_pdf.insert_pdf(doc, from_page=page_num, to_page=page_num)

        pdf_bytes = new_pdf.write()
        new_pdf.close()

        # Save the split PDF to the current section
        section.section_file.save(
            f"section_{split_index+1}.pdf",  # Naming based on split_index (repeating)
            ContentFile(pdf_bytes)
        )

        section.save()

def section_complete(request,slot_id):
    if request.method == 'POST':
        slot = TimeSlots.objects.get(pk=slot_id)
        slot.section_status = True
        slot.time_status = True
        slot.save()
    return redirect('schedules')




def merge_pdfs_in_memory(timeslots):
    """Merges PDFs from TimeSlots where section_status is False."""
    pdf_merger = fitz.open()
    
    # Fetch all relevant TimeSlots instances

    if not timeslots.exists():
        print("No matching TimeSlots with section_status=False found!")
        return None

    # Merge PDFs
    for slot in timeslots:
        if slot.section_file:  # Ensure file exists
            pdf_merger.insert_pdf(fitz.open(stream=slot.section_file.read(), filetype="pdf"))
        if slot.time_status:
            slot.section_status = True
            slot.not_complete = True
            slot.save()
    print("PDFs merged in memory.")
    return pdf_merger




def split_merged_pdf(merged_pdf,num_splits,section_list):
    doc = merged_pdf
    total_pages = len(doc)
    
    pages_per_split = total_pages // num_splits

    for i, section in enumerate(section_list):
    # Determine which split this section should belong to (cycling through first num_splits)
        split_index = i % num_splits  

        start_page = split_index * pages_per_split
        end_page = start_page + pages_per_split

        if split_index == num_splits - 1:
            end_page = total_pages  # Ensure last split gets remaining pages

        # Create a new PDF for this section
        new_pdf = fitz.open()
        for page_num in range(start_page, end_page):
            new_pdf.insert_pdf(doc, from_page=page_num, to_page=page_num)

        pdf_bytes = new_pdf.write()
        new_pdf.close()

        # Save the split PDF to the current section
        section.section_file.save(
            f"section_{split_index+1}.pdf",  # Naming based on split_index (repeating)
            ContentFile(pdf_bytes)
        )

        section.section_status =False
    

        section.save()





import fitz  # PyMuPDF
import io

def process_pdf(pdf_path):
    # Extract text from the input PDF
    input_doc = fitz.open(pdf_path)
    text = ""
    for page in input_doc:
        text += page.get_text("text") + "\n"
    input_doc.close()
    
    # Detect sections in the document
    sections = {}
    current_section = "Introduction"
    sections[current_section] = ""
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.isupper() or line.startswith("Chapter") or line[0].isdigit():
            current_section = line
            sections[current_section] = ""
        else:
            sections[current_section] += line + "\n"
    
    # Generate the output PDF
    output_doc = fitz.open()
    page_width, page_height = 595, 842  # A4 dimensions in points
    margins, column_gap = 50, 20
    
    for section, content in sections.items():
        stripped_content = content.strip()
        if not stripped_content or len(stripped_content.split()) <= 10:
            continue
        
        lines = [line.strip() for line in stripped_content.split('\n') if line.strip()]
        if not lines:
            continue
        
        page = output_doc.new_page()
        y_position = margins
        
        # Determine the best font size to fit content in one column
        initial_font = 12
        min_font = 3
        best_font = None
        heading_font = 14
        
        for test_font in range(initial_font, min_font - 1, -1):
            line_height = test_font * 1.2
            max_lines = (page_height - 2 * margins - heading_font * 2) // line_height
            if len(lines) <= max_lines:
                best_font = test_font
                break
        
        if best_font is not None:
            # Single column layout with determined font size
            page.insert_text((margins, y_position), section, 
                            fontname="Helvetica-Bold", fontsize=heading_font)
            y_position += heading_font * 2
            for line in lines:
                page.insert_text((margins, y_position), line, 
                                fontname="Times-Roman", fontsize=best_font)
                y_position += best_font * 1.2
        else:
            # Two-column layout with minimum font size
            content_font = min_font
            line_height = content_font * 1.2
            max_lines_col = int((page_height - 2 * margins - heading_font * 2) // line_height)
            max_lines_col = max(1, max_lines_col)
            split_index = min(max_lines_col, len(lines))
            left_lines = lines[:split_index]
            right_lines = lines[split_index:]
            
            page.insert_text((margins, y_position), section, 
                            fontname="Helvetica-Bold", fontsize=heading_font)
            y_position += heading_font * 2
            
            col_width = (page_width - 2 * margins - column_gap) // 2
            x_right = margins + col_width + column_gap
            
            def add_column(x_start, column_lines):
                y = y_position
                for line in column_lines:
                    if y + line_height > page_height - margins:
                        break
                    page.insert_text((x_start, y), line, 
                                    fontname="Times-Roman", fontsize=content_font)
                    y += line_height
            
            add_column(margins, left_lines)
            add_column(x_right, right_lines)
    
    # Save the generated PDF to a bytes buffer and return
    buffer = io.BytesIO()
    output_doc.save(buffer)
    pdf_bytes = buffer.getvalue()
    output_doc.close()
    buffer.close()
    
    return pdf_bytes

