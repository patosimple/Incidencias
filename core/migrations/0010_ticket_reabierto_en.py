from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_lecturaticket"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="reabierto_en",
            field=models.DateTimeField(
                blank=True,
                help_text="Fecha de la última reapertura (CERRADO -> REABIERTO)",
                null=True,
            ),
        ),
    ]