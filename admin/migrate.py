import wsgiref.handlers
from datetime import datetime
import random
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.db import GqlQuery
from model import *

class DoMigration(webapp.RequestHandler):
    def get(self):
        self.add_selectors(Quiz)
        self.remove_maxvalue(Session)
        return
   
    def add_selectors(self, type):
        objects = type.all().fetch(1000)
        self.response.out.write('Updating %s ...<br>' % (type.__name__,))
        update_count = 0
        for o in objects:
            selector = AutoquizQuestionSelector.gql('where quiz = :1 and user = :2', o, o.owner).get()
            if not selector:
                selector = AutoquizQuestionSelector()
                selector.init(o, o.owner)
                selector.put()
                self.response.out.write('Added selector for quiz %s (owner=%s)<br>' % (o.key(), o.owner.nickname()))
                update_count += 1
            
            subscriptions = Subscription.gql('where quiz = :1', o).fetch(1000)
            for subscription in subscriptions:
                selector = AutoquizQuestionSelector.gql('where quiz = :1 and user = :2', o, subscription.user).get()
                if not selector:
                    selector = AutoquizQuestionSelector()
                    selector.init(o, subscription.user)
                    selector.put()
                    self.response.out.write('Added selector for quiz %s (subscription user=%s)<br>' % (o.key(), subscription.user.nickname()))
                    update_count += 1
        self.response.out.write('Updated %d record(s) of type %s<br>' % (update_count, type.__name__))

    def remove_maxvalue(self, type):
        objects = type.all().fetch(1000)
        self.response.out.write('Updating %s ...<br>' % (type.__name__,))
        update_count = 0
        for o in objects:
            if o.autoquiz_value:
                o.autoquiz_value = None
                o.put()
                update_count += 1
        self.response.out.write('Updated %d record(s) of type %s<br>' % (update_count, type.__name__))

    def update_objects(self, type):
        objects = type.all().fetch(1000)
        self.response.out.write('Updating %s ...<br>' % (type.__name__,))
        update_count = 0
        for o in objects:
            if o.value > 1:
                o.value = random.random()
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