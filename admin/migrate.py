import wsgiref.handlers
from datetime import datetime
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.db import GqlQuery
from quizlink import Quiz
from quizlink import Question
from quizlink import Session
from quizlink import Response
from quizlink import Comment

class DoMigration(webapp.RequestHandler):
    def get(self):
        self.update_objects(Question)
        return
        
    def update_objects(self, type):
        objects = type.all().fetch(1000)
        self.response.out.write('Updating %s ...<br>' % (type.__name__,))
        update_count = 0
        for o in objects:
            if o.comment_count is None:
                comment_count = Comment.gql('where question = :1', o).count(1000)
                o.comment_count = comment_count
                self.response.out.write('%d comments for question %s<br>' % (o.comment_count, o.key()))
                o.put()
                update_count += 1
        self.response.out.write('Updated %d record(s) of type %s<br>' % (update_count, type.__name__))

def main():
    application = webapp.WSGIApplication(
                                       [('/migrate', DoMigration)
                                        ],
                                       debug=True)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
    main()