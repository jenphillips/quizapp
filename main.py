import os
import json
import datetime

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.properties import StringProperty
from kivy.uix.screenmanager import ScreenManager, FallOutTransition
from kivy.factory import Factory

from chart import AutoAxisTimeSeriesChart


def today():
    return datetime.datetime.now().strftime("%Y%m%d")


def json_from_file(filename):
    with open(filename) as f:
        return json.load(f)


class QuirkRoot(ScreenManager):
    active_questionnaire = StringProperty()

    def __init__(self, **kwargs):
        super(QuirkRoot, self).__init__(**kwargs)

        self.transition = FallOutTransition()
        self.scores = {}
        self.responses = {}

        home_screen = self.get_screen('home')

        # Populate home screen with available questionnaires
        for filename in os.listdir(os.getcwd() + "/questionnaires"):
            if not filename.startswith('.'):  # Ignore .DS_store :/
                path = os.path.join("questionnaires", filename)
                questionnaire_json = json_from_file(path)
                title = questionnaire_json['title']
                selector = Factory.QuestionnaireSelector()
                selector.title = title
                selector.filename = filename

                home_screen.content.add_widget(selector)

    def load_questionnaire(self, filename):
        screen = self.get_screen('questionnaire')
        self.active_questionnaire = filename
        path = os.path.join("questionnaires", filename)
        questionnaire_json = json_from_file(path)

        screen.clear_widgets()
        screen.question_manager = ScreenManager()
        screen.add_widget(screen.question_manager)
        self.responses = {}
        self.scores = {}

        for question in questionnaire_json['questions']:
            q = Factory.Question()
            q.name = question['name']
            q.text = question['text']
            q.group = question['average_group']

            if question['type'] == "range":
                # Build list of response options
                for n in range(question['value_min'], question['value_max']):
                    option = Button(text=str(n))
                    option.bind(on_press=self.handle_response)
                    q.content.add_widget(option)

            screen.question_manager.add_widget(q)

        self.current = 'questionnaire'

    def handle_response(self, instance):
        manager = self.get_screen("questionnaire").question_manager
        question = manager.current_screen
        response = instance.text

        if question.group not in self.scores:
            self.scores[question.group] = 0
        self.scores[question.group] += int(response)

        # Save list of (date, score) tuples for each average group
        if question.group not in self.responses:
            self.responses[question.group] = []

        self.responses[question.group] = (today(), self.scores[question.group])

        # print self.responses

        if manager.next() == manager.screen_names[0]:
            # User has finished questionnaire. Save scores:
            self.save_score()
            # Display scores to user, divided by group:
            screen = self.get_screen('score')
            screen.score_display.clear_widgets()
            for g, s in self.scores.iteritems():
                label = Label(text="Score for group %s: %d" % (g, s))
                screen.score_display.add_widget(label)
            self.current = 'score'
        else:
            # Advance to next question
            manager.current = manager.next()

    def score_path(self, questionnaire_filename):
        score_filename = (
            QuirkApp.get_running_app().user_data_dir +
            os.sep +
            os.path.splitext(questionnaire_filename)[0] +
            '.json'
        )
        return os.path.join("scores", score_filename)

    def save_score(self):
        '''
        Write score data to json. Date is stored in one file
        per questionnaire. Format is:

        {
            '<average_group>': [
                [YYYYMMDD, <score>],
                [YYYYMMDD, <score>]
        }
        '''
        path = self.score_path(self.active_questionnaire)
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        try:
            with open(path, 'r') as file:
                scores = json.load(file)
        except Exception:
            scores = {}

        for group, (date, score) in self.responses.iteritems():
            group_list = scores.setdefault(group, [])
            group_list.append((date, score))

        with open(path, 'w') as file:
            json.dump(scores, file)
        self.current = "home"

    def view_chart(self, questionnaire_filename):
        path = self.score_path(questionnaire_filename)

        try:
            with open(path) as file:
                data_points = json.load(file)
        except Exception:
            data_points = {}

        self.get_screen('chart').time_series_chart.clear_time_series()

        for group, time_series in data_points.items():
            self.get_screen('chart').time_series_chart.add_time_series(
                [
                        (datetime.datetime.strptime(v[0], "%Y%m%d").date(), v[1])
                        for v in time_series
                ], group)

        # process all the lines
        self.current = "chart"


class QuirkApp(App):
    def on_pause(self):
        return True

    def on_resume(self):
        pass

    def on_start(self):
        Window.bind(on_keyboard=self.back_key_handler)

    def back_key_handler(self, window, keycode, *args):
        if keycode == 27 and self.root.current != "home":
            self.root.current = "home"
            return True
        return False


if __name__ == '__main__':
    QuirkApp().run()
