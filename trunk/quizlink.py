# quizlink.py
# main module. defines request handlers for url endpoints

import sys
import os
import wsgiref.handlers
import random
from datetime import datetime
from sets import Set
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.ext.db import GqlQuery
from model import *

FETCH_SIZE = 1000
RESPONSE_BATCH_SIZE = 50
COMMENT_COUNT = 10
PAGE_LIMIT = 50

class QuizProvider():
	def get_owned_quizzes(self, user):
		owned_gql = 'where owner = :1 and deleted = False order by taken_count desc'
		owned_quizzes = Quiz.gql(owned_gql, user).fetch(FETCH_SIZE)
		return owned_quizzes
	
	def get_subscriptions(self, user):
		subscriptions_query = Subscription.gql('where user = :1', user)
		subscriptions = [subscription for subscription in subscriptions_query.fetch(FETCH_SIZE)
				 if not subscription.quiz.deleted and subscription.quiz.public]
		return subscriptions
	
	def get_public_quizzes(self):
		quizzes = Quiz.gql('where public = True and deleted = False order by taken_count desc').fetch(FETCH_SIZE)
		return quizzes

class MainPage(webapp.RequestHandler):
	def get(self):
		user = users.get_current_user()
		provider = QuizProvider()
		latest_comments = Comment.gql('where quizowner = :1 order by dateadded desc', user).fetch(COMMENT_COUNT)
		
		template_values = { 
			'user':user, 
			'isadmin':users.is_current_user_admin(),
			'subscriptions':provider.get_subscriptions(user), 
			'owned_quizzes':provider.get_owned_quizzes(user),
			'latest_comments':latest_comments,
			'logout_url':users.create_logout_url('/')
			}
		path = os.path.join(os.path.dirname(__file__), 'templates/mainpage.html')
		self.response.out.write(template.render(path, template_values))

class AddQuiz(webapp.RequestHandler):
	def post(self):
		quiz = Quiz()
		quiz.title = self.request.get('title').strip()
		
		if not quiz.title:
			self.redirect(self.request.headers['referer'])
			return
		user = users.get_current_user()
		quiz.owner = user
		quiz.public = False
		quiz.deleted = False
		quiz.taken_count = 0
		quiz.question_count = 0
		quiz.put()
		
		selector = AutoquizQuestionSelector()
		selector.init(quiz, user)
		selector.put()
		
		self.redirect('/questions?quiz=%s' % (quiz.key(),))

class QuestionList(webapp.RequestHandler):
	def get(self):
		quiz = db.get(self.request.get('quiz'))
		first = get_positive_number(self.request.get('first'))
		isowner = quiz.owner == users.get_current_user()
		if not isowner and not quiz.public:
			# cannot view the questions of another user's private quiz
			self.redirect('/')
			return
		questions = Question.gql('where quiz = :1 order by dateadded', quiz).fetch(PAGE_LIMIT, first)
		template_values = { 
			'isowner':isowner,
			'quiz':quiz,
			'questions':questions
			}
		template_values.update(paging_dictionary(first, questions, quiz.question_count))
		path = os.path.join(os.path.dirname(__file__), 'templates/questionlist.html')
		self.response.out.write(template.render(path, template_values))

class AddQuestion(webapp.RequestHandler):
	def get(self):
		quiz = db.get(self.request.get('quiz'))
		template_values = { 
			'quiz':quiz
			}
		path = os.path.join(os.path.dirname(__file__), 'templates/addquestion.html')
		self.response.out.write(template.render(path, template_values))
	
	def post(self):
		quiz = db.get(self.request.get('quiz'))
		if quiz.owner != users.get_current_user():
			# cannot add questions to another user's quiz
			self.redirect('/')
			return
		question = Question()
		question.quiz = quiz
		question.text = self.request.get('questiontext').strip()
		question.image_url = self.request.get('image_url')
		question.audio_url = self.request.get('audio_url')
		question.type = self.request.get('questiontype')
		question.comment_count = 0
		question.put()
		
		quiz.question_count += 1
		quiz.put()
		self.redirect('/editquestion?question=%s' % (question.key(),))


class EditQuestion(webapp.RequestHandler):
	def get(self):
		question = db.get(self.request.get('question'))
		template_values = { 'question':question }
		path = os.path.join(os.path.dirname(__file__), 'templates/editquestion.html')
		self.response.out.write(template.render(path, template_values))
		
	def post(self):
		question = db.get(self.request.get('question'))
		if question.quiz.owner != users.get_current_user():
			# cannot edit another user's question
			self.redirect('/')
			return
		question.text = self.request.get('questiontext').strip()
		question.image_url = self.request.get('image_url')
		question.audio_url = self.request.get('audio_url')
		question.type = self.request.get('questiontype')
		question.put()
		self.redirect('/editquestion?question=%s' % (question.key(),))
	
class AddChoice(webapp.RequestHandler):
	def post(self):
		question = db.get(self.request.get('question'))
		if question.quiz.owner != users.get_current_user():
			# cannot add choices to another user's questions
			self.redirect('/')
			return
		choice = Choice()
		choice.question = question
		choice.text = self.request.get('choice').strip()
		choice.correct = self.request.get('correct') == "true"
		choice.put()
		self.redirect(self.request.headers['referer'])

class ToggleCorrect(webapp.RequestHandler):
	def get(self):
		choice = db.get(self.request.get('choice'))
		if choice.question.quiz.owner != users.get_current_user():
			# cannot toggle another user's choice
			self.redirect('/')
			return
		choice.correct = not choice.correct
		choice.put()
		self.redirect(self.request.headers['referer'])
	
class CopyQuestion(webapp.RequestHandler):
	def get(self):
		question = db.get(self.request.get('question'))
		user = users.get_current_user()
		provider = QuizProvider()
		quizzes = provider.get_owned_quizzes(user)
		template_values = {
			'question':question,
			'quizzes':quizzes,
			'operation':'copy'
			}
		path = os.path.join(os.path.dirname(__file__), 'templates/selectquizzes.html')
		self.response.out.write(template.render(path, template_values))
		
	def post(self):
		question = db.get(self.request.get('question'))
		quiz = db.get(self.request.get('quiz'))
		# cannot copy a question into another user's quiz
		if quiz.owner == users.get_current_user():
			question.copyto(quiz)
		self.redirect('/questions?quiz=%s' % (quiz.key(),))

class MoveQuestion(webapp.RequestHandler):
	def get(self):
		question = db.get(self.request.get('question'))
		user = users.get_current_user()
		provider = QuizProvider()
		quizzes = [quiz for quiz in provider.get_owned_quizzes(user) if quiz.key() != question.quiz.key()]
		template_values = {
			'question':question,
			'quizzes':quizzes,
			'operation':'move'
			}
		path = os.path.join(os.path.dirname(__file__), 'templates/selectquizzes.html')
		self.response.out.write(template.render(path, template_values))
		
	def post(self):
		question = db.get(self.request.get('question'))
		original_quiz = question.quiz
		quiz = db.get(self.request.get('quiz'))
		# cannot move a question from another user's quiz
		# cannot move a question into another user's quiz
		if question.quiz.owner == users.get_current_user() and quiz.owner == users.get_current_user():
			question.moveto(quiz)
		self.redirect('/questions?quiz=%s' % (original_quiz.key(),))
	
	
class RenameQuiz(webapp.RequestHandler):
	def get(self):
		quiz = db.get(self.request.get('quiz'))
		template_values = { 'quiz':quiz }
		path = os.path.join(os.path.dirname(__file__), 'templates/renamequiz.html')
		self.response.out.write(template.render(path, template_values))
	
	def post(self):
		quiz = db.get(self.request.get('quiz'))
		# cannot rename another user's quiz
		if quiz.owner == users.get_current_user():
			quiz.title = self.request.get('title')
		quiz.put()
		self.redirect('/')
	
class AddComment(webapp.RequestHandler):
	def post(self):
		question = db.get(self.request.get('question'))
		user = users.get_current_user()
		comment = Comment()
		comment.question = question
		comment.text = self.request.get('comment_text').strip()
		
		if comment.text:
			comment.user = user
			comment.quizowner = question.quiz.owner
			comment.byowner = (user == comment.quizowner)
			comment.put()
			question.comment_count += 1
			question.put()
		
		session_key = self.request.get('session')
		if session_key:
			number = long(self.request.get('number'))
			self.redirect('/ask?session=%s&number=%s' % (session_key, number + 1))
		else:
			self.redirect(self.request.headers['referer'])
	
class CommentList(webapp.RequestHandler):
	def get(self):
		question = db.get(self.request.get('question'))
		comments = Comment.gql('where question = :1', question).fetch(FETCH_SIZE)
		isowner = (question.quiz.owner == users.get_current_user())
		template_values = {
			'comments':comments,
			'question':question,
			'isowner':isowner
			}
		path = os.path.join(os.path.dirname(__file__), 'templates/commentlist.html')
		self.response.out.write(template.render(path, template_values))


class PublicList(webapp.RequestHandler):
	def get(self):
		provider = QuizProvider()
		quizzes = provider.get_public_quizzes()
		template_values = { 'quizzes':quizzes }
		path = os.path.join(os.path.dirname(__file__), 'templates/publiclist.html')
		self.response.out.write(template.render(path, template_values))
		
class PublishQuiz(webapp.RequestHandler):
	def get(self):
		quiz = db.get(self.request.get('quiz'))
		if users.get_current_user() == quiz.owner:
			quiz.public = True
			quiz.put()
		self.redirect('/')
		
class DepublishQuiz(webapp.RequestHandler):
	def get(self):
		quiz = db.get(self.request.get('quiz'))
		if users.get_current_user() == quiz.owner:
			quiz.public = False
			quiz.put()
		self.redirect('/')
		
class SubscribeToQuiz(webapp.RequestHandler):
	def get(self):
		quiz = db.get(self.request.get('quiz'))
		user = users.get_current_user()
		subscription = Subscription.gql('where quiz = :1 and user = :2', quiz, user).get()
		if not subscription:
			subscription = Subscription()
			subscription.quiz = quiz
			subscription.user = user
			subscription.put()
			
			selector = AutoquizQuestionSelector.gql('where quiz = :1 and user = :2', quiz, user).get()
			if not selector:
				selector = AutoquizQuestionSelector()
				selector.init(quiz, user)
				selector.put()
		self.redirect('/')

class TakeQuiz(webapp.RequestHandler):
	def get(self):
		quiz = db.get(self.request.get('quiz'))
		sessions = Session.gql('where quiz = :1 and user = :2 and deleted = False',
				       quiz, users.get_current_user()).fetch(FETCH_SIZE)
		incomplete_sessions = [session for session in sessions if not session.timecompleted]
		template_values = {
			'quiz':quiz,
			'incomplete_sessions':incomplete_sessions
			}
		path = os.path.join(os.path.dirname(__file__), 'templates/startquiz.html')
		self.response.out.write(template.render(path, template_values))
		
	def post(self):
		user = users.get_current_user()
		quiz = db.get(self.request.get('quiz'))

		session = Session()
		session.init(user)
		session.quiz = quiz
		session.mode = self.request.get('mode')
		session.put()
		self.redirect('/ask?session=%s&number=%d' % (session.key(), 1))
		
			
class AskQuestion(webapp.RequestHandler):
	def get(self):
		session = db.get(self.request.get('session'))
		number = long(self.request.get('number'))
		response = self.get_next_response(session, number)
				
		if not response:
			# if we could not retrieve a response, we've reached the end of the quiz
			self.session_completed(session)
			return
			
		question = response.question # access property to fetch from database
		choices = list(question.choices)
		random.shuffle(choices)
		template_values = { 
			'response':response,
			'question':response.question,
			'choices':choices
			}
		path = os.path.join(os.path.dirname(__file__), 'templates/askquestion.html')
		self.response.out.write(template.render(path, template_values))
		
	def get_next_response(self, session, number):
		if session.mode == "AUTO":
			return self.grab_autoquiz_response(session, number)
		
		responseQuery = Response.gql('where session = :1 and number = :2', session, number)
		response = responseQuery.get()
		if not response:
			# if there is no response object in the database, grab the next batch
			self.grab_batch(session, number)
			response = responseQuery.get()
		if not response:
			# there are no more regular responses, so see if there is a retry
			response = self.grab_retry(session, number)
		return response
		

	def grab_batch(self, session, current_number):
		# prepare responses for each question to be asked
		number = current_number
		questions = list(Question.gql('where quiz = :1 and dateadded > :2', 
			session.quiz, session.max_question_dateadded).fetch(RESPONSE_BATCH_SIZE))
		random.shuffle(questions)
		for question in questions:
			response = Response()
			response.init(session, question, number)
			response.put()
			number += 1
			if question.dateadded > session.max_question_dateadded:
				session.max_question_dateadded = question.dateadded
		session.put()

	def grab_retry(self, session, number):
		retry = Retry.gql('where session = :1 order by rand', session).get()
		if not retry:
			return None
		response = Response()
		response.init(session, retry.question, number)
		response.put()
		return response
	
	def grab_autoquiz_response(self, session, number):
		user = users.get_current_user()
		
		if number > session.question_limit:
			return None
		
		selectors = list(AutoquizQuestionSelector.gql('where user = :1 and enabled = True', user).fetch(FETCH_SIZE))
		# pick a random test to select a question from
		random.shuffle(selectors)
		selector = selectors[0]
		# the selector keeps track of the max dateadded of all questions that have been answered,
		# so to select the next question, we will request one that is greater than this max dateadded
		question = Question.gql('where quiz = :1 and dateadded > :2 order by dateadded', selector.quiz, selector.max_dateadded).get()
		
		# if there wasn't a question, we've selected all of the questions from this quiz.
		# now we can start pulling autoquizQuestions. get the question with the lowest value
		if not question:
			autoquizQuestion = AutoquizQuestion.gql('where user = :1 and quiz = :2 order by value', user, selector.quiz).get()
			question = autoquizQuestion.question
		
		response = Response()
		response.init(session, question, number)
		response.put()
		return response
		
	def session_completed(self, session):
		session.timecompleted = datetime.now()
		session.put()

		if session.mode == "AUTO":
			quiztitle = "Auto Quiz"
		else:
			quiz = session.quiz
			quiz.taken_count += 1
			quiz.put()
			quiztitle = quiz.title

		template_values = { 
			'quiztitle':quiztitle, 
			'session':session
			}
		path = os.path.join(os.path.dirname(__file__), 'templates/quizdone.html')
		self.response.out.write(template.render(path, template_values))
		
class GradeResponse(webapp.RequestHandler):
	def post(self):
		number = long(self.request.get('number'))
		session_key = self.request.get('session_key')
		response = db.get(self.request.get('response_key'))
		if response is None:
			# response could have been deleted if question was deleted
			self.redirect('/ask?session=%s&number=%d' % (session_key, number))
			return
		answers = [choice.text.lower().strip() for choice in response.question.choices if choice.correct]
		
		if not response.answered:
			self.grade(response, answers)
			self.handle_retry(response)
			self.update_autoquiz(response)
			response.answered = True
			response.put()
			
			session = response.session
			session.questions_answered += 1
			if response.correct:
				session.number_correct += 1
			session.percentage_correct = float(session.number_correct)/session.questions_answered*100
			session.put()
		
		comments = Comment.gql('where question = :1 order by dateadded desc', response.question).fetch(COMMENT_COUNT)

		template_values = {
			'response':response,
			'comments':comments,
			'isowner':(response.question.quiz.owner == users.get_current_user()),
			'none_of_the_above':not answers
		}
		path = os.path.join(os.path.dirname(__file__), 'templates/showanswer.html')
		self.response.out.write(template.render(path, template_values))
		
	def grade(self, response, answers):
		if response.question.type == "MCMR":
			responseList = list(self.request.get_all('response_text'))
			response.text = ', '.join(responseList)
			response.correct = Set([r.lower().strip() for r in responseList]) == Set(answers)
		else:
			response.text = self.request.get('response_text')
			response.correct = response.text.lower().strip() in answers
			
	def handle_retry(self, response):
		session = response.session
		question = response.question
		retry = Retry.gql('where session = :1 and question = :2',
				  session, question).get()
	
		if not retry:
			if session.mode == "RET" and not response.correct:
				retry = Retry()
				retry.session = session
				retry.question = question
				retry.rand = random.random()
				retry.put()
		elif response.correct:
			db.delete(retry)
		else:
			# stick this question at the end
			retry.rand += question.quiz.question_count + random.random()
			retry.put()
			
	def update_autoquiz(self, response):
		user = users.get_current_user()
		question = response.question
		selector = AutoquizQuestionSelector.gql('where user = :1 and quiz = :2', user, question.quiz).get()
		if not selector:
			return
		
		if question.dateadded > selector.max_dateadded:
			# inform the selector that a question with a more recent dateadded has been answered
			selector.max_dateadded = question.dateadded
		
		session = response.session
		autoquizQuestion = AutoquizQuestion.gql('where user = :1 and question = :2', user, question).get()
		if not autoquizQuestion:
			autoquizQuestion = AutoquizQuestion()
			autoquizQuestion.init(question, user)

		# Compute a new question value between the current value (V) and the
		# selector's max_value (M). The new value will be a random number between
		# Cmin or Imin and Cmax or Imax, depending on whether the question was answered
		# correctly (Cmin-Cmax) or incorrectly (Imin-Imax)
		#                    Cmin                             Cmax
		#                    [-- range for correct response --]
		# V ------------------------------------------------- M
		#        [-- range for incorrect response --]
		#        Imin                               Imax
		# By design, Cmin > Imin, so incorrect questions have a greater chance of being asked than
		# correct ones. Also, Imax converges towards Imin the more the question is answered incorrectly.
		
		# M - V
		distance = selector.max_value - autoquizQuestion.value

		if response.correct:
			# assign Cmin, Cmax
			if autoquizQuestion.incorrect_bias > 0:
				autoquizQuestion.incorrect_bias -= 1
			domain_min = autoquizQuestion.value + 0.50 * distance
			domain_max = selector.max_value
		else:
			# assign Imin, Imax
			autoquizQuestion.incorrect_bias += 1
			bias = 0.6 - 0.1 * autoquizQuestion.incorrect_bias
			domain_min = autoquizQuestion.value + 0.20 * distance
			domain_max = autoquizQuestion.value + bias * distance

		autoquizQuestion.value = domain_min + random.random() * (domain_max - domain_min)

		# widen the total range a bit for each response
		selector.max_value += 0.005
		selector.put()
			
		autoquizQuestion.put()
	

class ResumeSession(webapp.RequestHandler):
	def get(self):
		session = db.get(self.request.get('session'))
		lastresponse = Response.gql('where session = :1 and answered = False order by number', session).get()
		if lastresponse:
			self.redirect('/ask?session=%s&number=%d' % (session.key(), lastresponse.number))
			return
		# if there wasn't a response, try one after the last one asked. there may be retries
		lastresponse = Response.gql('where session = :1 order by number desc', session).get()
		if lastresponse:
			self.redirect('/ask?session=%s&number=%d' % (session.key(), lastresponse.number + 1))
			return
		# if we still can't find a response, go to the first question
		self.redirect('/ask?session=%s&number=%d' % (session.key(), 1))
		
class SessionList(webapp.RequestHandler):
	def get(self):
		user = users.get_current_user()
		quiz = db.get(self.request.get('quiz'))
		first = get_positive_number(self.request.get('first'))
		sessions = Session.gql('where quiz = :1 and user = :2 and deleted = False order by timestarted desc', quiz, user).fetch(PAGE_LIMIT, first)
		session_count = Session.gql('where quiz = :1 and user = :2 and deleted = False', quiz, user).count()
		
		template_values = {
			'quiz':quiz, 
			'sessions':sessions 
			}
		template_values.update(paging_dictionary(first, sessions, session_count))
		path = os.path.join(os.path.dirname(__file__), 'templates/sessionlist.html')
		self.response.out.write(template.render(path, template_values))
		
class ResponseList(webapp.RequestHandler):
	def get(self):
		session = db.get(self.request.get('session'))
		first = get_positive_number(self.request.get('first'))
		responses = Response.gql('where session = :1 order by number', session).fetch(PAGE_LIMIT, first)
		total_responses = Response.gql('where session = :1', session).count()
		template_values = { 
			'session':session,
			'responses':responses
			}
		template_values.update(paging_dictionary(first, responses, total_responses))
		path = os.path.join(os.path.dirname(__file__), 'templates/responselist.html')
		self.response.out.write(template.render(path, template_values))

class DeleteItem(webapp.RequestHandler):
	def get(self):
		user = users.get_current_user()
		if self.request.get('quiz'):
			self.markquiz_fordeletion(db.get(self.request.get('quiz')), user)
		if self.request.get('question'):
			self.deletequestion(db.get(self.request.get('question')), user)
		if self.request.get('choice'):
			self.deletechoice(db.get(self.request.get('choice')), user)
		if self.request.get('comment'):
			self.deletecomment(db.get(self.request.get('comment')), user)
		if self.request.get('session'):
			self.marksession_fordeletion(db.get(self.request.get('session')), user)
		if self.request.get('subscription'):
			self.deletesubscription(db.get(self.request.get('subscription')), user)
		self.redirect(self.request.headers['referer'])
	
	def markquiz_fordeletion(self, quiz, user):
		if user != quiz.owner and not users.is_current_user_admin():
			return
		quiz.deleted = True
		quiz.put()
	
	def marksession_fordeletion(self, session, user):
		if user != session.user:
			return
		session.deleted = True
		session.put()
	
	def deletequiz(self, quiz):
		for session in quiz.sessions:
			self.deletesession(session)
		for question in quiz.questions:
			self.deletequestion(question, users.get_current_user(), True)
		for subscription in quiz.subscriptions:
			db.delete(subscription)
		for selector in quiz.question_selectors:
			db.delete(selector)
		db.delete(quiz)
		
	def deletesession(self, session):
		for response in session.responses:
			db.delete(response)
		db.delete(session)
		
	def deletesubscription(self, subscription, user):
		selector = AutoquizQuestionSelector.gql('where quiz = :1 and user = :2', subscription.quiz, user).get()
		if selector:
			selector.enabled = False
			selector.put()
		db.delete(subscription)
		
	def deletequestion(self, question, user, deleting_quiz=False):
		if user != question.quiz.owner and not users.is_current_user_admin():
			return
		for choice in question.choices:
			self.deletechoice(choice, user)
		for response in question.responses:
			db.delete(response)
		for autoquiz_question in question.autoquiz_questions:
			db.delete(autoquiz_question)
		for comment in question.comments:
			self.deletecomment(comment, user, True)
		for retry in question.retries:
			db.delete(retry)
		
		if not deleting_quiz:
			question.quiz.question_count -= 1
			question.quiz.put()
		db.delete(question)

	def deletecomment(self, comment, user, deleting_question=False):
		if user != comment.question.quiz.owner and not users.is_current_user_admin():
			return

		if not deleting_question:
			comment.question.comment_count -= 1
			comment.question.put()
		db.delete(comment)
		
	def deletechoice(self, choice, user):
		if user != choice.question.quiz.owner and not users.is_current_user_admin():
			return
		db.delete(choice)
		
class AutoquizSetup(webapp.RequestHandler):
	def get(self):
		user = users.get_current_user()
		selectors = [selector for selector in self.get_selectors(user) if selector.quiz.question_count > 0]
		sessions = Session.gql("where user = :1 and mode = 'AUTO' and deleted = False order by timestarted desc", user).fetch(FETCH_SIZE)
		
		template_values = {
			'selectors':selectors,
			'sessions':sessions
			}
		path = os.path.join(os.path.dirname(__file__), 'templates/autoquiz.html')
		self.response.out.write(template.render(path, template_values))
	
	def post(self):
		quizzes = list(self.request.get_all('quiz'))
		user = users.get_current_user()
		selectors = self.get_selectors(user)

		one_enabled = False
		for selector in selectors:
			selector.enabled = str(selector.quiz.key()) in quizzes
			if selector.enabled:
				one_enabled = True
			selector.put()

		if not one_enabled:
			self.redirect('/autoquiz')
			return

		session = Session()
		session.init(user)
		session.mode = "AUTO"
		session.question_limit = int(self.request.get('question_count'))
		session.put()
		self.redirect('/ask?session=%s&number=1' % (session.key(),))
		
	def get_selectors(self, user):
		selectors = AutoquizQuestionSelector.gql('where user = :1', user).fetch(FETCH_SIZE)
		return selectors

def main():
	application = webapp.WSGIApplication(
		[('/', MainPage),
		     ('/publiclist', PublicList), 
		     ('/publish', PublishQuiz), 
		     ('/depublish', DepublishQuiz), 
		     ('/subscribe', SubscribeToQuiz),
		     ('/questions', QuestionList), 
		     ('/addquiz', AddQuiz), 
		     ('/editquestion', EditQuestion),
		     ('/addquestion', AddQuestion), 
		     ('/addchoice', AddChoice),
		     ('/copyquestion', CopyQuestion),
		     ('/movequestion', MoveQuestion),
		     ('/rename', RenameQuiz),
		     ('/toggle', ToggleCorrect),
		     ('/comment', AddComment),
		     ('/comments', CommentList),
		     ('/take', TakeQuiz), 
		     ('/ask', AskQuestion), 
		     ('/grade', GradeResponse),
		     ('/resume', ResumeSession),
		     ('/sessions', SessionList), 
		     ('/responses', ResponseList),
		     ('/delete', DeleteItem),
		     ('/autoquiz', AutoquizSetup)
		     ], 
		debug=True)
	wsgiref.handlers.CGIHandler().run(application)

def get_positive_number(value):
	if not value:
		return 0
	number = int(value)
	if number < 0:
		return 0
	return number

def paging_dictionary(first, batch, total_count):
	return {
		'atfirst':first <= 0,
		'atlast':first + len(batch) >= total_count,
		'first':first,
		'last':first + len(batch),
		'previous':first - PAGE_LIMIT,
		'count':PAGE_LIMIT
		}

if __name__ == "__main__":
	main()