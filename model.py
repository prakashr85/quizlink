# model.py
# defines database model objects for quizlink

from google.appengine.ext import db
from datetime import datetime

EPOCH=datetime(1980,1,1)

class Quiz(db.Model):
	title = db.StringProperty()
	owner = db.UserProperty()
	public = db.BooleanProperty()
	deleted = db.BooleanProperty()
	taken_count = db.IntegerProperty()
	question_count = db.IntegerProperty()

class Question(db.Model):
	quiz = db.ReferenceProperty(Quiz, collection_name="questions")
	type = db.StringProperty()
	text = db.StringProperty(multiline=True)
	dateadded = db.DateTimeProperty(auto_now_add=True)
	comment_count = db.IntegerProperty()
	image_url = db.StringProperty()
	audio_url = db.StringProperty()
	
	def copyto(self, quiz):
		question_copy = Question()
		question_copy.quiz = quiz
		question_copy.type = self.type
		question_copy.text = self.text
		question_copy.deleted = False
                question_copy.comment_count = 0
		question_copy.put()
		for choice in self.choices:
			choice_copy = Choice()
			choice_copy.question = question_copy
			choice_copy.text = choice.text
			choice_copy.correct = choice.correct
			choice_copy.put()
                question_copy.quiz.question_count += 1
                question_copy.quiz.put()
	
class Choice(db.Model):
	question = db.ReferenceProperty(Question, collection_name="choices")
	text = db.StringProperty()
	correct = db.BooleanProperty()

class Session(db.Model):	
	quiz = db.ReferenceProperty(Quiz, collection_name="sessions")
	user = db.UserProperty()
	number_correct = db.IntegerProperty()
	questions_answered = db.IntegerProperty()
	percentage_correct = db.FloatProperty()
	max_question_dateadded = db.DateTimeProperty()
	timestarted = db.DateTimeProperty(auto_now_add=True)
	timecompleted = db.DateTimeProperty()
	mode = db.StringProperty()
	deleted = db.BooleanProperty()
	autoquiz_value = db.FloatProperty()
	
	def init(self, user):
		self.number_correct = 0
		self.percentage_correct = 0.0
		self.questions_answered = 0
		self.max_question_dateadded = EPOCH
		self.user = user
		self.deleted = False

class Response(db.Model):
	session = db.ReferenceProperty(Session, collection_name="responses")
	question = db.ReferenceProperty(Question, collection_name="responses")
	number = db.IntegerProperty()
	text = db.StringProperty()
	correct = db.BooleanProperty()
	answered = db.BooleanProperty()
	
	def init(self, session, question, number):
		self.session = session
		self.question = question
		self.number = number
		self.answered = False

class Retry(db.Model):
	session = db.ReferenceProperty(Session, collection_name="retries")
	question = db.ReferenceProperty(Question, collection_name="retries")
	rand = db.FloatProperty()
	
class Subscription(db.Model):
	quiz = db.ReferenceProperty(Quiz, collection_name="subscriptions")
	user = db.UserProperty()
	
class Comment(db.Model):
	question = db.ReferenceProperty(Question, collection_name="comments")
	text = db.StringProperty(multiline=True)
	user = db.UserProperty()
	dateadded = db.DateTimeProperty(auto_now_add=True)
	byowner = db.BooleanProperty()
	quizowner = db.UserProperty()

class AutoquizQuestionSelector(db.Model):
	user = db.UserProperty()
	quiz = db.ReferenceProperty(Quiz, collection_name="question_selectors")
	max_dateadded = db.DateTimeProperty()
	max_value = db.FloatProperty()
	enabled = db.BooleanProperty()
	correct_count = db.IntegerProperty()
	incorrect_count = db.IntegerProperty()
	
	def init(self, quiz, user):
		self.quiz = quiz
		self.user = user
		self.max_dateadded = EPOCH
		self.max_value = 0.0
		self.enabled = False
		
class AutoquizQuestion(db.Model):
	user = db.UserProperty()
	quiz = db.ReferenceProperty(Quiz, collection_name="autoquiz_questions")
	question = db.ReferenceProperty(Question, collection_name="autoquiz_questions")
	value = db.FloatProperty()
	incorrect_bias = db.IntegerProperty()
	
	def init(self, question, user):
		self.question = question
		self.quiz = question.quiz
		self.user = user
		self.value = 0.0
		self.incorrect_bias = 0