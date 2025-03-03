from django.db import models
from users.models import Pdf
# Create your models here.

class sections(models.Model):
    section_file = models.FileField(upload_to='uploads/sections', null=True, blank=True)
    pdf = models.ForeignKey(Pdf,on_delete=models.CASCADE,related_name='sections')
    status = models.BooleanField(default=False)

    def delete(self, *args, **kwargs):
        self.section_file.delete()
        super().delete(*args, **kwargs)

    def __str__(self):
        return  self.section_file.name if self.section_file else "No file"
    
class TimeSlots(models.Model):
    tpdf = models.ForeignKey(Pdf,on_delete=models.CASCADE,related_name='time_slots')
    start_time = models.DateTimeField(null=True,blank=True)
    end_time = models.DateTimeField(null=True,blank=True)
    section = models.OneToOneField(sections,on_delete=models.CASCADE,related_name='time_slot',null=True,blank=True)
    time_status = models.BooleanField(default=False)

    def __str__(self):
        if self.start_time and self.end_time:
            return f"{self.start_time.strftime('%Y-%b-%d %I:%M %p')} - {self.end_time.strftime('%Y-%b-%d %I:%M %p')}"
        elif self.start_time:
            return self.start_time.strftime('%Y-%b-%d %I:%M %p')
        elif self.end_time:
            return self.end_time.strftime('%Y-%b-%d %I:%M %p')
        else:
            return "--:--"

    
    