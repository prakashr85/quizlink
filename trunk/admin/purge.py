import wsgiref.handlers
from datetime import datetime
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.db import GqlQuery

from quizlink import Quiz
from quizlink import Question
from quizlink import Session
from quizlink import Response
from quizlink import DeleteItem

class PurgeRequest(webapp.RequestHandler):
    def get(self):
        deleteItem = DeleteItem()
        self.purge(Quiz, deleteItem.deletequiz)
        self.purge(Session, deleteItem.deletesession)
        
    def purge(self, type, callback):
        delete_count = 0
        objects = type.gql('where deleted = True').fetch(1000)
        for o in objects:
            if o.deleted:
                callback(o)
                self.response.out.write('Deleted %s %s<br>' % (type.__name__, o.key()))
                delete_count += 1
        self.response.out.write('Deleted %d object(s) of type %s<br>' % (delete_count, type.__name__))
        pass

def main():
    application = webapp.WSGIApplication(
                                       [('/purge', PurgeRequest)
                                        ],
                                       debug=True)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
    main()