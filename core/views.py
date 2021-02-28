from django.views.generic import TemplateView

class Index(TemplateView):
    template_name = 'core/index.html'
index = Index.as_view()

# KEEP THIS ISOLATED
# We're eventually exporting this to tickle

CSV_FORM_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Title</title>
</head>
<body>
    <form action="" method="POST" enctype="multipart/form-data">
        <label for="file"> Upload a file</label>
        <input type="file" id="file" name="{}">
        <small>Only accepts CSV files</small>
        <button type="submit">Upload</button>
    </form>
</body>
</html>
'''

TICK_FORM_TEMPLATE = CSV_FORM_TEMPLATE.format('ticks_csv')
TODO_FORM_TEMPLATE = CSV_FORM_TEMPLATE.format('todos_csv')

SPORT_ROUTE_TYPES = (
    'Sport',
    'Sport, TR',
    'Sport, Alpine',
)

TRAD_ROUTE_TYPES = (
    'Trad',
    'Trad, TR',
    'Trad, Alpine',
)

BOULDER_ROUTE_TYPES = ('Boulder',)
ROUTE_ROUTE_TYPES = SPORT_ROUTE_TYPES + TRAD_ROUTE_TYPES

import csv
from io import TextIOWrapper
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from tickle.models import Attempt, Area, Route, Boulder, Pitch, Todo

def read_csv_rows(request, file_name):
    csv_bytes_file = request.FILES[file_name]

    if not csv_bytes_file.name.endswith('.csv'):
        raise Exception()

    csv_utf8_file = TextIOWrapper(csv_bytes_file, 'utf-8')

    csv_file = csv.DictReader(csv_utf8_file)

    return csv_file

def get_area_from_mountainproject_location_string(location_string):
    area = None

    for area_name in location_string.split('>'):
        area, created = Area.objects.get_or_create(
            parent=area,
            name=area_name.strip(),
        )

    return area

def get_boulder_or_route_from_row(row):
    boulder = None
    route = None

    area = get_area_from_mountainproject_location_string(row['Location'])

    if row['Route Type'] == 'Boulder':
        boulder, created = Boulder.objects.get_or_create(
            area=area,
            name=row['Route'],
            difficulty=row['Rating'],
            mountainproject=row['URL'],
        )
    elif row['Route Type'] in ROUTE_ROUTE_TYPES:
        route, created = Route.objects.get_or_create(
            area=area,
            name=row['Route'],
            protection_style=row['Route Type'], # TODO This is wrong
            mountainproject=row['URL'],
        )

        pitch_count = int(row['Pitches'])

        for i in range(pitch_count):
            pitch, created = Pitch.objects.get_or_create(
                order=i + 1,
                route=route,
                difficulty=row['Rating'],
            )
    else:
        raise Exception('Unable to determine climb from row {}'.format(row))

    return boulder, route

@csrf_exempt
def import_ticks(request):
    if not request.user.is_superuser:
        raise Exception()
    if request.method == 'GET':
        return HttpResponse(TICK_FORM_TEMPLATE)
    elif request.method == 'POST':
        csv_file = read_csv_rows(request, 'ticks_csv')

        for row in csv_file:
            attempt_kwargs = {}

            attempt_kwargs['user'] = request.user
            attempt_kwargs['date'] = row['Date']
            attempt_kwargs['notes'] = row['Notes']

            attempt_kwargs['boulder'], attempt_kwargs['route'] = get_boulder_or_route_from_row(row)

            if row['Style'] == 'Lead':
                if row['Lead Style'] in ('Flash', 'Onsight', 'Redpoint'):
                    attempt_kwargs['result'] = 'send'
                elif row['Lead Style'] == '':
                    attempt_kwargs['result'] = 'unknown'
                elif row['Lead Style'] == 'Fell/Hung':
                    attempt_kwargs['result'] = 'fall'
                else:
                    raise Exception(
                        'Unable to determine result from row {}'.format(row),
                    )
            elif row['Style'] in ('', 'Follow', 'TR'):
                attempt_kwargs['result'] = 'unknown'
            elif row['Style'] in ('Send', 'Solo'):
                attempt_kwargs['result'] = 'send'
            elif row['Style'] == '':
                if row['Route Type'] == 'Boulder':
                    attempt_kwargs['result'] = 'send'
                else:
                    raise Exception(
                        'Unable to determine result from row {}'.format(row),
                    )
            else:
                raise Exception(
                    'Unable to determine result from row {}'.format(row),
                )

            if row['Style'] == 'Lead' and row['Lead Style'] == 'Onsight':
                attempt_kwargs['prior_knowledge'] = False
            else:
                attempt_kwargs['prior_knowledge'] = True

            if row['Route Type'] == 'Boulder':
                attempt_kwargs['protection_used'] = 'pad'
            elif row['Style'] == 'Lead':
                if row['Route Type'] in ('TR',) + TRAD_ROUTE_TYPES:
                    attempt_kwargs['protection_used'] = 'gear'
                elif row['Route Type'] in SPORT_ROUTE_TYPES:
                    attempt_kwargs['protection_used'] = 'bolts'
                else:
                    raise Exception(
                        'Unable to determine protection used from row {}'.format(row),
                    )
            elif row['Style'] in ('Follow', 'TR'):
                attempt_kwargs['protection_used'] = 'tr'
            elif row['Style'] == 'Solo':
                attempt_kwargs['protection_used'] = 'none'
            else:
                raise Exception(
                    'Unable to determine protection used from row {}'.format(row),
                )

            Attempt.objects.get_or_create(**attempt_kwargs)

        return HttpResponse('success')
    else:
        raise Exception()

@csrf_exempt
def import_todos(request):
    if not request.user.is_superuser:
        raise Exception()
    if request.method == 'GET':
        return HttpResponse(TODO_FORM_TEMPLATE)
    elif request.method == 'POST':
        csv_file = read_csv_rows(request, 'todos_csv')

        for row in csv_file:
            todo_kwargs = {}

            todo_kwargs['user'] = request.user
            todo_kwargs['boulder'], todo_kwargs['route'] = get_boulder_or_route_from_row(row)

            route_type = row['Route Type']

            if route_type == 'Boulder':
                todo_kwargs['protection'] = 'pad'
            elif route_type in TRAD_ROUTE_TYPES:
                todo_kwargs['protection'] = 'gear'
            elif route_type in SPORT_ROUTE_TYPES:
                todo_kwargs['protection'] = 'bolts'
            elif route_type == 'TR':
                todo_kwargs['protection'] = 'tr'
            else:
                raise Exception(
                    'Unable to determine protection from row {}'.format(row),
                )

            todo_kwargs['style'] = 'other'

            Todo.objects.get_or_create(**todo_kwargs)

        return HttpResponse('success')
    else:
        raise Exception()

from django.contrib.auth.models import User
from django.views.generic import DetailView, ListView

class ClimbingProfile(DetailView):
    model = User
    template_name = 'tickle/user_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.object

        context['attempts'] = user.attempts.all()[:10]
        context['todos'] = user.todos.all()[:10]

        return context
climbing_profile = ClimbingProfile.as_view()

class ClimbingAttempts(ListView):
    model = Attempt
    def get_queryset(self):
        pk = self.kwargs['pk']
        return User.objects.get(pk=pk).attempts.order_by('-date')
climbing_attempts = ClimbingAttempts.as_view()

class ClimbingTodos(ListView):
    model = Todo
    def get_queryset(self):
        pk = self.kwargs['pk']
        return User.objects.get(pk=pk).todos.all()
climbing_todos = ClimbingTodos.as_view()
