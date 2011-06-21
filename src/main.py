import logging
from datetime import datetime,timedelta
from google.appengine.api import images, urlfetch
from google.appengine.ext import db, webapp
from google.appengine.ext.webapp.util import run_wsgi_app

class Profile(db.Model):
    image = db.BlobProperty()
    updated_at = db.DateTimeProperty(auto_now=True)
    
    def should_refresh_image(self):
        yesterday = datetime.now() - timedelta(hours=6)
        return yesterday > self.updated_at


class AvatarImageManipulator():
    def __init__(self,image,size=80):
        self.img = image
        self.size = size
        
    def manipulate(self):
        self._scale()
        data = self._crop()
        return data
    
    def _scale(self):
        img = self.img
        if img.width < img.height:
            img.resize(width=self.size)
        else:
            img.resize(height=self.size)
        return img.execute_transforms()
    
    def _crop(self):
        if self.img.width < self.img.height:
            self._crop_from_corner()
        else:
            self._crop_from_center()
        return self.img.execute_transforms()
        
    def _crop_from_corner(self):
        size = self.size * 1.0
        self.img.crop(0.0, 0.0, size / self.img.width, size / self.img.height)
        
    def _crop_from_center(self):
        size = self.size * 1.0
        width = self.img.width
        height = self.img.height
        def calc_small_ratio(s,d):
            return (d-s)/2.0/d
        def calc_big_ratio(s,d):
            return (d+s)/2.0/d
        self.img.crop(calc_small_ratio(size, width),
                      calc_small_ratio(size, height), 
                      calc_big_ratio(size, width), 
                      calc_big_ratio(size, height))
    

class MainPage(webapp.RequestHandler):

    def get_fb_graph_url(self, facebook_id,size):
        return "http://graph.facebook.com/%s/picture?type=%s" % (facebook_id, size)

    def get_fb_image(self, facebook_id):
        result = urlfetch.fetch(self.get_fb_graph_url(facebook_id,'large'))
        if 'error' in result.content: 
            raise "no result from facebook"
        img_data = result.content
        img = images.Image(str(img_data))
        return img

    def generate_facebook_avatar(self, facebook_id):
        img = self.get_fb_image(facebook_id)
        if img is None:
            raise "no Image created"
        size = 80
        if self.request.get('size'):
            size = int(self.request.get('size'))
        img_data = AvatarImageManipulator(img,size).manipulate()
        p = Profile.get_or_insert(facebook_id)
        p.image = img_data
        p.put()
        return p

    def get(self,facebook_id):
        try:
            p = Profile.get_by_key_name(facebook_id)
            if p is None or self.request.get("refresh") or p.should_refresh_image():
                p = self.generate_facebook_avatar(facebook_id)
                
            self.response.headers['Content-Type'] = "image/jpg"
            self.response.out.write(p.image)
            
        except Exception,e:
            logging.error(e)
            self.redirect(self.get_fb_graph_url(facebook_id,'square'), False)
            
application = webapp.WSGIApplication([
                                      (r'/fb/(\d+)', MainPage)
                                      ], debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
