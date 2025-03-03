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
    date = models.DateField(null=True,blank=True)
    start_time = models.TimeField(null=True,blank=True)
    end_time = models.TimeField(null=True,blank=True)
    section = models.OneToOneField(sections,on_delete=models.CASCADE,related_name='time_slot',null=True,blank=True)
    time_status = models.BooleanField(default=False)

    def __str__(self):
        start_str = self.start_time.strftime('%I:%M %p') if self.start_time else "--:--"
        end_str = self.end_time.strftime('%I:%M %p') if self.end_time else "--:--"

        if self.start_time and self.end_time:
            return f"{start_str} - {end_str}"
        return start_str if self.start_time else end_str
    class Meta:
        ordering = ['date', 'start_time']

    
    