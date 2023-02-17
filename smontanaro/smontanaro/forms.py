#!/usr/bin/env python3

"The forms used in the app - probably should be divided among application modules"

from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, HiddenField, SelectField
from wtforms.validators import DataRequired

class PhotoForm(FlaskForm):
    "simple form for generating links to Google Photo images"
    url = StringField('Google Photo Image Page:', validators=[DataRequired()])
    width = IntegerField('width', default=800)
    fmt = SelectField('format', choices=[
        ("HTML", "<HTML>"),
        ("BBCode", "[BBCode]"),
        ("Raw", "Raw"),
    ], default="BBCode")

class TopicForm(FlaskForm):
    "simple form used to add topics to a message"
    topic = StringField('Add Topic(s):', validators=[DataRequired()])
    year = HiddenField('year')
    month = HiddenField('month')
    seq = HiddenField('seq')

class SearchForm(FlaskForm):
    "simple form used to search Brave for archived list messages"
    query = StringField('Search:', validators=[DataRequired()])
    site = HiddenField('site', default='smontanaro.net')
    engine = SelectField('Engine:', choices=[
        ('Brave', 'Brave'),
        ('DuckDuckGo', 'DuckDuckGo'),
        ('Bing', 'Bing'),
        ('Google', 'Google'),
        ('Neeva', 'Neeva'),
    ], default='Brave')

class QueryForm(FlaskForm):
    "simple query form used to search for indexed phrases"
    query = StringField('Search:', validators=[DataRequired()])
