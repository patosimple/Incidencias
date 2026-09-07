import nh3

from django import forms
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm

from .models import Ticket, Comentario, Usuario


class UsuarioCreationForm(UserCreationForm):
    """Form de alta de usuario del admin: muestra los mismos campos que la
    edición (datos personales, permisos y rol) para poder asignarlos al crear.
    El campo `rol` es obligatorio (igual que en editar, con la opción vacía
    "-----" por defecto). password1/password2 (del UserCreationForm) manejan
    la contraseña; se excluyen los campos automáticos del modelo
    (password, date_joined, last_login)."""

    class Meta:
        model = Usuario
        fields = (
            "username",
            "rol",
            "first_name",
            "last_name",
            "email",
            "is_staff",
            "is_active",
            "is_superuser",
            "groups",
            "user_permissions",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = None
        self.fields["password1"].help_text = None

# Tags/atributos que Quill genera con formato seguro (sin scripts ni eventos).
# nh3 elimina por defecto <script>, eventos inline (onerror, onclick, ...) y
# URLs peligrosas (javascript:); acá solo ampliamos la lista blanca base.
_QUILL_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "s", "strike",
    "ol", "ul", "li",
    "blockquote", "code", "pre",
    "h1", "h2", "h3",
    "a", "img",
}
_QUILL_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title"},
}


def _sanear_html(html):
    """Sanea el HTML que genera Quill: conserva el formato básico permitido
    y elimina scripts/eventos/URLs peligrosas (mitigación de XSS)."""
    if not html:
        return html
    return nh3.clean(html, tags=_QUILL_TAGS, attributes=_QUILL_ATTRIBUTES)


_PASSWORD_INPUT_CSS = (
    "w-full text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-100 "
    "border border-gray-300 dark:border-slate-600 rounded px-3 py-1.5 "
    "focus:outline-none focus:ring-1 focus:ring-brand-500"
)


class CambioPasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Contraseña actual"
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password2"].label = "Repetí la nueva contraseña"
        for campo in self.fields.values():
            campo.widget.attrs["class"] = _PASSWORD_INPUT_CSS
            campo.help_text = ""


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["sistema", "titulo", "descripcion_original"]
        widgets = {
            "descripcion_original": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Un solicitante solo puede elegir entre los sistemas a los que tiene acceso.
        # El superuser ve todos los sistemas (mismo bypass que en listado/detalle).
        if usuario is not None and not usuario.is_superuser:
            self.fields["sistema"].queryset = self.fields["sistema"].queryset.filter(
                usuariosistema__usuario=usuario
            )

    def clean_descripcion_original(self):
        return _sanear_html(self.cleaned_data.get("descripcion_original"))


class TicketEditarForm(forms.ModelForm):
    """Edición de ticket por el solicitante dueño: solo título y descripción
    (el sistema no se cambia: reasignarlo rompería la visibilidad por sistema).
    El widget de descripción es un textarea oculto que alimenta el editor Quill
    (mismo patrón que ComentarioForm.cuerpo)."""

    class Meta:
        model = Ticket
        fields = ["titulo", "descripcion_original"]
        widgets = {
            "descripcion_original": forms.Textarea(attrs={"class": "hidden"}),
        }

    def clean_descripcion_original(self):
        return _sanear_html(self.cleaned_data.get("descripcion_original"))


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = Comentario
        fields = ["cuerpo"]
        widgets = {
            "cuerpo": forms.Textarea(attrs={"rows": 3, "placeholder": "Escriba una respuesta...", "class": "hidden"}),
        }

    def clean_cuerpo(self):
        return _sanear_html(self.cleaned_data.get("cuerpo"))
