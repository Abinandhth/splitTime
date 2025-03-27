from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, logout as authlogout, login as authlogin
from django.contrib.auth.decorators import login_required
from users.models import Pdf,Settings
from datetime import datetime, timedelta,date
from pdf.models import TimeSlots
import fitz
from django.core.files.base import ContentFile
from django.db.models import Q
import os
from io import BytesIO
from django.urls import reverse
from django.utils import timezone
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar
import re


@login_required(login_url='/login/')
def sections(request):
    pdfs = Pdf.objects.filter(user=request.user)
    settings = Settings.objects.get(user_settings=request.user)

    return render(request, 'sections.html', {
        'pdfs': pdfs,
        'from_time': settings.from_time.strftime('%H:%M'),
        'to_time': settings.to_time.strftime('%H:%M'),
        'duration': settings.duration.total_seconds() // 60,
    })


@login_required(login_url='/login/')
def schedules(request):
    pdfs = Pdf.objects.filter(user=request.user)
    
    # Get selected date from request or use today
    selected_date = request.GET.get('date')
    if selected_date:
        try:
            selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            selected_date = date.today()
    else:
        selected_date = date.today()

    schedules = []
    for pdf in pdfs:
        time_slots = TimeSlots.objects.filter(tpdf=pdf, date=selected_date).order_by('start_time')
        if not time_slots.exists():
            continue

        dates_dict = {}
        for slot in time_slots:
            date_str = slot.date.strftime('%d/%m/%Y')
            dates_dict.setdefault(date_str, []).append({
                'time': f"{slot.start_time.strftime('%I:%M%p')}-{slot.end_time.strftime('%I:%M%p')}",
                'section_url': slot.section_file.url if slot.section_file else None,
                'section_status': slot.section_status,
                'time_status': slot.time_status,
                'not_complete':slot.not_complete,
                'id': slot.pk,
                'structured':slot.tpdf.structured
            })

        schedules.append({
            'pdf_name': pdf.title,
            'dates': [{'date': date, 'slots': slots} for date, slots in dates_dict.items()]
        })

    return render(request, 'schedules.html', {
        'schedules': schedules,
        'selected_date': selected_date.strftime('%Y-%m-%d')
    })


@login_required(login_url='/login/')
def reschedule_schedule(request,slot_id):
    if request.method == 'POST':
        from_time = request.POST.get('from_time')
        to_time = request.POST.get('to_time')

        if not (from_time and to_time ):
            return redirect('schedules')  # Redirect if invalid data

        try:
            from_time = datetime.strptime(from_time, "%H:%M").time()
            to_time = datetime.strptime(to_time, "%H:%M").time()
        except ValueError:
            return redirect('schedules')
        
        slot = TimeSlots.objects.get(pk=slot_id)
        slot.start_time = from_time
        slot.end_time = to_time
        slot.save()

        return redirect(reverse('schedules'))
    return redirect('schedules')


@login_required(login_url='/login/')
def pdf_reschedule(request,pk):
    if request.method == 'POST':
        pdf_title = request.POST.get('pdfTitle')
        deadline = request.POST.get('deadline')

        if pdf_title:

            pdf_obj = Pdf.objects.get(pk=pk)
            pdf_obj.deadline = deadline
            pdf_obj.title = pdf_title
            pdf_obj.save()

            total_updated_slots = TimeSlots.objects.filter(tpdf=pdf_obj,section_status=False)
  
            merged_pdf = merge_pdfs_in_memory(total_updated_slots)
            print("merged")

            
           

            selected_timeslots_json = request.POST.get('selected_timeslots', '')
            import json
            try:
                selected_timeslots = json.loads(selected_timeslots_json)
                    
                # Parse the deadline string to a date object
                deadline_date = datetime.strptime(deadline, '%Y-%m-%d').date()
                today = datetime.now().date()
                slots_count=0
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
                        slots_count+=1
                        
                        # Move to the next day
                    current_date += timedelta(days=1)

                total_time = TimeSlots.objects.filter(tpdf=pdf_obj).count()
                print(total_time)

                user_settings = Settings.objects.get(user_settings=request.user)
                min_section = user_settings.min

                pdf_obj.total_noof_timeslots = total_time
                pdf_obj.save()
                print("saved")
            
            
                
                
            except json.JSONDecodeError:
                print("Error decoding selected time slots JSON")
            except ValueError as e:
                print(f"Error parsing date or time: {e}")

            if merged_pdf:  # Check if merged_pdf is not None
                split_and_store_pdf(merged_pdf, slots_count, min_section, pdf_obj)
            else:
                print("No PDFs merged; skipping split.")
                    

        else:
            # Update settings only if values are provided
            user_settings = Settings.objects.get(user_settings=request.user)  # Add this line
            min_val = request.POST.get('min')
            if min_val and min_val.strip():
                user_settings.min = int(min_val)

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
    return redirect('sections')


def merge_pdfs_in_memory(timeslots):
    """Merges PDFs from TimeSlots where section_status is False."""
    pdf_merger = fitz.open()
    
    # Fetch all relevant TimeSlots instances

    if not timeslots.exists():
        print("No matching TimeSlots with section_status=False found!")
        return None

    # Merge PDFs
    for slot in timeslots: # Ensure file exists
        pdf_merger.insert_pdf(fitz.open(stream=slot.section_file.read(), filetype="pdf"))
        slot.delete()

    print("PDFs merged in memory.")
    return pdf_merger


def split_and_store_pdf(merged_pdf,num_splits,min,pdf_obj):
    doc = merged_pdf
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

    section_list = list(TimeSlots.objects.filter(tpdf=pdf_obj,section_status=False).order_by('date', 'start_time'))

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


def upload_pdf(request,pk):
    if request.method == 'POST':
        slot = TimeSlots.objects.get(pk=pk)
        uploaded_file = slot.section_file
        html_content = generate_html_content(uploaded_file)
        return render(request, 'result.html', {'html_content': html_content})






def is_bold(element):
    for text_line in element:
        if hasattr(text_line, "_objs"):
            for char in text_line._objs:
                if isinstance(char, LTChar) and "Bold" in char.fontname:
                    return True
    return False

def clean_text(text):
    text = re.sub(r' +', ' ', text)
    return text.strip()

def generate_html_content(uploaded_file):
    html_elements = []
    
    # Read uploaded file into a seekable buffer
    pdf_content = uploaded_file.read()
    pdf_file = BytesIO(pdf_content)
    pdf_file.seek(0)
    
    for page_num, page_layout in enumerate(extract_pages(pdf_file)):
        page_content = []
        heading = None
        
        elements = [e for e in page_layout if isinstance(e, LTTextContainer)]
        
        if elements:
            x0, y0, x1, y1 = page_layout.bbox
            midpoint = (x0 + x1) / 2
            
            left_col = []
            right_col = []
            for element in elements:
                center_x = (element.x0 + element.x1) / 2
                if center_x < midpoint:
                    left_col.append(element)
                else:
                    right_col.append(element)
            
            left_col_sorted = sorted(left_col, key=lambda e: -e.y1)
            right_col_sorted = sorted(right_col, key=lambda e: -e.y1)
            sorted_elements = left_col_sorted + right_col_sorted
        else:
            sorted_elements = []
        
        # Find heading
        for element in sorted_elements:
            if is_bold(element):
                heading = clean_text(element.get_text())
                break
        
        # Process elements
        for element in sorted_elements:
            text = clean_text(element.get_text())
            if not text:
                continue
            
            if text == heading:
                page_content.append(f'<h2 class="page-heading">{text}</h2>')
                heading = None
                continue
            
            text_with_breaks = text.replace('\n', '<br>')
            page_content.append(f'<p>{text_with_breaks}</p>')

        html_elements.extend(page_content)
        html_elements.append(f'<div class="page-break">Page {page_num+1}</div>')
    
    return ''.join(html_elements)