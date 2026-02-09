from django.db import migrations

def create_admin(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    email = 'weinemandela@gmail.com'
    username = email
    password = 'wmm@343@'

    user = User.objects.filter(username=username).first()
    if user:
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        return

    User.objects.create_superuser(username=username, email=email, password=password)


def rollback_admin(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username='weinemandela@gmail.com').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gym', '0002_memberprofile_user_workoutplan'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(create_admin, rollback_admin),
    ]
