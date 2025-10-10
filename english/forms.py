
from django import forms
from .models import Comment

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ваш комментарий...'}),
        }



# в шаблоне не в модальном окне указать валидность
# интеграция с телеграм сайт нужно сделать бесплатным

