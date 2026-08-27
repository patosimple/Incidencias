from django import forms

from .models import Ticket, Comentario, Adjunto


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["sistema", "titulo", "descripcion_original"]
        widgets = {
            "descripcion_original": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Un solicitante solo puede elegir entre los sistemas a los que tiene acceso
        if usuario is not None:
            self.fields["sistema"].queryset = self.fields["sistema"].queryset.filter(
                usuariosistema__usuario=usuario
            )


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = Comentario
        fields = ["cuerpo"]
        widgets = {
            "cuerpo": forms.Textarea(attrs={"rows": 3, "placeholder": "Escriba una respuesta..."}),
        }


class AdjuntoForm(forms.ModelForm):
    class Meta:
        model = Adjunto
        fields = ["archivo", "tipo_archivo"]


# Para permitir subir varios adjuntos en el mismo request de creación de ticket
AdjuntoFormSet = forms.modelformset_factory(Adjunto, form=AdjuntoForm, extra=3, can_delete=False)
