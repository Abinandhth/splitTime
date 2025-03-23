from django.db import models
from users.models import Pdf
# Create your models here.

class TimeSlots(models.Model):
    tpdf = models.ForeignKey(Pdf, on_delete=models.CASCADE, related_name='time_slots')
    date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    section_file = models.FileField(upload_to='uploads/sections', null=True, blank=True)
    section_status = models.BooleanField(default=False)
    time_status = models.BooleanField(default=False)
    not_complete = models.BooleanField(default=False)

    def __str__(self):
        if self.section_file:
            return self.section_file.name
        start_str = self.start_time.strftime('%I:%M %p') if self.start_time else "--:--"
        end_str = self.end_time.strftime('%I:%M %p') if self.end_time else "--:--"
        return f"{start_str} - {end_str}" if self.start_time and self.end_time else start_str if self.start_time else end_str

    def delete(self, *args, **kwargs):
        if self.section_file:
            self.section_file.delete(save=False)
        super().delete(*args, **kwargs)

    class Meta:
        ordering = ['date', 'start_time']
