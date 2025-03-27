from django.db import models
from django.contrib.auth.models import User
import datetime

class Pdf(models.Model):
    pdf_file = models.FileField(upload_to='uploads/pdf/', null=True, blank=True)
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='pdfs')
    title = models.CharField(max_length=250,null=True,blank=True)
    deadline = models.DateField(null=True,blank=True)
    total_sections = models.IntegerField(null=True,blank=True)
    total_noof_timeslots = models.IntegerField(null=True,blank=True)
    revision = models.IntegerField(null=True,blank=True)
    structured = models.BooleanField(null=False,default=False)

    def __str__(self):
        return self.title if self.title else (self.pdf_file.name if self.pdf_file else "No file")
    
    def delete(self, *args, **kwargs):
        self.pdf_file.delete()
        super().delete(*args, **kwargs)
    
class Settings(models.Model):
    min = models.IntegerField(default=1,null=False)
    duration = models.DurationField(default=datetime.timedelta(minutes=30),null=False)  
    from_time = models.TimeField(default=datetime.time(18,0),null=False)
    to_time = models.TimeField(default=datetime.time(22,0),null=False)
    user_settings = models.OneToOneField(User,on_delete=models.CASCADE,related_name='user_setting')

    
   
