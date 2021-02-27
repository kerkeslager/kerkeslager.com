from django.views.generic import TemplateView

class Index(TemplateView):
    template_name = 'core/index.html'
index = Index.as_view()

# KEEP THIS ISOLATED
# We're eventually exporting this to tickle

TICK_FORM_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Title</title>
</head>
<body>
    <form action="" method="POST" enctype="multipart/form-data">
        <label for="file"> Upload a file</label>
        <input type="file" id="file" name="ticks_csv">
        <small>Only accepts CSV files</small>
        <button type="submit">Upload</button>
    </form>
</body>
</html>
'''

import csv
from io import StringIO
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from tickle.models import Attempt, Area, Route, Boulder, Pitch

@csrf_exempt
def import_ticks(request):
    if not request.user.is_superuser:
        raise Exception()
    if request.method == 'GET':
        return HttpResponse(TICK_FORM_TEMPLATE)
    elif request.method == 'POST':
        ticks_csv = request.FILES['ticks_csv']

        if not ticks_csv.name.endswith('.csv'):
            raise Exception()

        tick_data_string = ticks_csv.read().decode('utf-8')

        tick_data_io = StringIO(tick_data_string)

        csv_reader = csv.reader(tick_data_io)

        headers = {}
        rows = []

        for row in csv_reader:
            if headers:
                rows.append({
                    headers[index]: cell
                    for index, cell in enumerate(row)
                })
            else:
                for index, header in enumerate(row):
                    headers[index] = header

        for row in rows:
            attempt_kwargs = {}

            attempt_kwargs['user'] = request.user
            attempt_kwargs['date'] = row['Date']
            attempt_kwargs['notes'] = row['Notes']

            area = None

            for area_name in row['Location'].split('>'):
                area, created = Area.objects.get_or_create(
                    parent=area,
                    name=area_name.strip(),
                )

            if row['Route Type'] in ('Sport', 'Sport, TR', 'TR', 'Trad', 'Trad, TR'):
                route, created = Route.objects.get_or_create(
                    area=area,
                    name=row['Route'],
                    protection_style=row['Route Type'],
                    mountainproject=row['URL'],
                )

                pitch_count = int(row['Pitches'])

                for i in range(pitch_count):
                    pitch, created = Pitch.objects.get_or_create(
                        order=i + 1,
                        route=route,
                        difficulty=row['Rating'],
                    )

                attempt_kwargs['route'] = route
            elif row['Route Type'] == 'Boulder':
                boulder, created = Boulder.objects.get_or_create(
                    area=area,
                    name=row['Route'],
                    difficulty=row['Rating'],
                    mountainproject=row['URL'],
                )

                attempt_kwargs['boulder'] = boulder
            else:
                import ipdb; ipdb.set_trace()

            if row['Style'] == 'Lead':
                if row['Lead Style'] in ('Flash', 'Onsight', 'Redpoint'):
                    attempt_kwargs['result'] = 'send'
                elif row['Lead Style'] == '':
                    attempt_kwargs['result'] = 'unknown'
                elif row['Lead Style'] == 'Fell/Hung':
                    attempt_kwargs['result'] = 'fall'
                else:
                    import ipdb; ipdb.set_trace()
            elif row['Style'] in ('', 'Follow', 'TR'):
                attempt_kwargs['result'] = 'unknown'
            elif row['Style'] in ('Send', 'Solo'):
                attempt_kwargs['result'] = 'send'
            elif row['Style'] == '':
                if row['Route Type'] == 'Boulder':
                    attempt_kwargs['result'] = 'send'
                else:
                    import ipdb; ipdb.set_trace()
            else:
                import ipdb; ipdb.set_trace()

            if row['Style'] == 'Lead':
                if row['Lead Style'] == 'Onsight':
                    attempt_kwargs['prior_knowledge'] = False
                elif row['Lead Style'] in ('', 'Flash', 'Fell/Hung', 'Redpoint'):
                    attempt_kwargs['prior_knowledge'] = True
                else:
                    import ipdb; ipdb.set_trace()
            elif row['Style'] in ('', 'Follow', 'Send', 'Solo', 'TR'):
                attempt_kwargs['prior_knowledge'] = True
            else:
                import ipdb; ipdb.set_trace()

            if row['Route Type'] == 'Boulder':
                attempt_kwargs['protection_used'] = 'pad'
            elif row['Style'] in ('', 'Lead'):
                if row['Route Type'] in ('TR', 'Trad', 'Trad, TR'):
                    attempt_kwargs['protection_used'] = 'gear'
                elif row['Route Type'] == 'Sport':
                    attempt_kwargs['protection_used'] = 'bolts'
                else:
                    import ipdb; ipdb.set_trace()
            elif row['Style'] in ('Follow', 'TR'):
                attempt_kwargs['protection_used'] = 'tr'
            elif row['Style'] == 'Solo':
                attempt_kwargs['protection_used'] = 'none'
            else:
                import ipdb; ipdb.set_trace()

            Attempt.objects.get_or_create(**attempt_kwargs)

        return HttpResponse('success')
    else:
        raise Exception()
