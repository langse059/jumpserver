# Generated by Django 3.1 on 2020-12-10 07:05

from django.db import migrations, models

TERMINAL_TYPE_KOKO = 'koko'
TERMINAL_TYPE_GUACAMOLE = 'guacamole'
TERMINAL_TYPE_OMNIDB = 'omnidb'


def migrate_terminal_type(apps, schema_editor):
    terminal_model = apps.get_model("terminal", "Terminal")
    db_alias = schema_editor.connection.alias
    terminals = terminal_model.objects.using(db_alias).all()
    for terminal in terminals:
        name = terminal.name.lower()
        if 'koko' in name:
            _type = TERMINAL_TYPE_KOKO
        elif 'gua' in name:
            _type = TERMINAL_TYPE_GUACAMOLE
        elif 'omnidb' in name:
            _type = TERMINAL_TYPE_OMNIDB
        else:
            _type = TERMINAL_TYPE_KOKO
        terminal.type = _type
    terminal_model.objects.bulk_update(terminals, ['type'])


class Migration(migrations.Migration):

    dependencies = [
        ('terminal', '0029_auto_20201116_1757'),
    ]

    operations = [
        migrations.AddField(
            model_name='terminal',
            name='type',
            field=models.CharField(choices=[('koko', 'KoKo'), ('guacamole', 'Guacamole'), ('omnidb', 'OmniDB')], default='koko', max_length=64, verbose_name='type'),
            preserve_default=False,
        ),
        migrations.RunPython(migrate_terminal_type)
    ]