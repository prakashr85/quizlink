import wsgiref.handlers
from datetime import datetime
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.db import GqlQuery
from model import *

class DoMigration(webapp.RequestHandler):
    def get(self):
        self.update_objects(Comment)
        return
        
    def update_objects(self, type):
        objects = type.all().fetch(1000)
        self.response.out.write('Updating %s ...<br>' % (type.__name__,))
        update_count = 0
        for o in objects:
            question = o.question
            if question:
                question_comment = QuestionComment.gql('where question = :1', question).fetch(1000)
                if not question_comment:
                    question_comment = QuestionComment()
                    question_comment.question = question
                    question_comment.comment = o
                    question_comment.put()
                    o.question = None
                    o.put()
                    self.response.out.write('Migrated comment %s<br>' % (o.key(), ))
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