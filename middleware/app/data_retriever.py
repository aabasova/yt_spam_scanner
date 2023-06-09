import os
import httplib2
import spacy
import googleapiclient
import googleapiclient.discovery

from oauth2client import client, GOOGLE_TOKEN_URI
from elasticsearch import helpers
from elasticsearch import Elasticsearch

from app.classifier import GenericClassifier

from dotenv import load_dotenv


# All secrets are stored a locally stored environment variables file
CLIENT_ID = os.getenv('V_CLIENT_ID')
CLIENT_SECRET = os.getenv('V_CLIENT_SECRET')
REFRESH_TOKEN = os.getenv('V_REFRESH_TOKEN')
DEVELOPER_KEY = os.getenv('V_DEVELOPER_KEY')


nlp = spacy.load("en_core_web_sm", disable=["ner"])


##################################### Data Retriever Class #####################################

class YtDataRetriever:
    """Provides an interface with the Youtube API"""

    def __init__(self):
        self._data_response = {}

        credentials = client.OAuth2Credentials(
            access_token=None,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            refresh_token=REFRESH_TOKEN,
            token_expiry=None,
            token_uri=GOOGLE_TOKEN_URI,
            user_agent=None,
            revoke_uri=None)

        self.http = credentials.authorize(httplib2.Http())


    
    # TODO old method that will be deleted soon (ok BUT still used!?)
    def get_video_data(self, video_id: str):

        # Disable OAuthlib's HTTPS verification when running locally.
        # *DO NOT* leave this option enabled in production.

        #os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = 'client_secret_737324637694-2c43sarhojqelig5rhvmp4pgkh8oiv5c.apps.googleusercontent.com.json'

        api_service_name = "youtube"
        api_version = "v3"

        youtube = googleapiclient.discovery.build(
            api_service_name, api_version, developerKey=DEVELOPER_KEY)

        self._data_response = self.get_video_comments(youtube, video_id)
        return self._data_response


    def get_comment_replies(self, service, comment_id):
        """obtains the replies of given comment"""
        request = service.comments().list(
            parentId=comment_id,
            part='id,snippet',
            maxResults=100
        )
        replies = []

        while request:
            response = request.execute()
            replies.extend(response['items'])
            request = service.comments().list_next(
                request, response)

        return replies


    def get_video_comments(self, service, video_id):
        """obtains the comments from given YouTube video via the YouTube API"""
        request = service.commentThreads().list(
            videoId=video_id,
            part='id,snippet,replies',
            maxResults=100
        )
        data = {}
        comments = []

        while request:
            response = request.execute()

            data['kind'] = response['kind']
            data['etag'] = response['etag']
            data['pageInfo'] = response['pageInfo']

            for comment in response['items']:
                reply_count = comment['snippet']['totalReplyCount']
                replies = comment.get('replies')
                if replies is not None and \
                        reply_count != len(replies['comments']):
                    replies['comments'] = self.get_comment_replies(service, comment['id'])

                # 'comment' is a 'CommentThreads Resource' that has it's
                # 'replies.comments' an array of 'Comments Resource'

                # Do fill in the 'comments' data structure
                # to be provided by this function:
                comments.append(comment)

            data['items'] = comments
            request = service.commentThreads().list_next(request, response)

        return data


##################################### YouTube Comment Class #####################################

class YtComment:
    """
    A data class that wraps around the Youtube comment
    representation that is returned by the official Youtube API
    """

    def __init__(self, data_item = None):
        if data_item is None: # reply
            self._id = None
            self._text_original = None
            self._author_name = None
            self._author_channel_url = None
            self._author_channel_id = None
            self._like_count = None
            self._publish_date = None
            self._is_reply = None
            self._parent_id = None

        else: # comment
            self._id = data_item["snippet"]["topLevelComment"]["id"]
            self._text_original = data_item['snippet']['topLevelComment']['snippet']['textOriginal'].strip().rstrip()
            self._author_name = data_item['snippet']['topLevelComment']['snippet']['authorDisplayName']
            self._author_channel_url = data_item["snippet"]["topLevelComment"]["snippet"]["authorChannelUrl"]
            self._author_channel_id = data_item["snippet"]["topLevelComment"]["snippet"]["authorChannelId"]["value"]
            self._like_count = data_item['snippet']['topLevelComment']['snippet']['likeCount']
            self._publish_date = data_item['snippet']['topLevelComment']['snippet']['publishedAt']
            self._is_reply = False
            self._parent_id = self._id

    def set_id(self, arg):
        self._id = arg

    def set_text_original(self, arg):
        self._text_original = arg

    def set_author_name(self, arg):
        self._author_name = arg

    def set_author_channel_url(self, arg):
        self._author_channel_url = arg

    def set_author_channel_id(self, arg):
        self._author_channel_id = arg

    def set_like_count(self, arg):
        self._like_count = arg

    def set_publish_date(self, arg):
        self._publish_date = arg

    def set_is_reply(self, arg):
        self._is_reply = arg

    def set_parent_id(self, arg):
        self._parent_id = arg

    def get_id(self):
        return self._id

    def get_text_original(self):
        return self._text_original

    def get_author_name(self):
        return self._author_name

    def get_author_channel_url(self):
        return self._author_channel_url

    def get_author_channel_id(self):
        return self._author_channel_id

    def get_like_count(self):
        return self._like_count

    def get_publish_date(self):
        return self._publish_date

    def get_is_reply(self):
        return self._is_reply

    def get_parent_id(self):
        return self._parent_id


##################################### YouTube Reply of Comment Class #####################################

class YtCommentReply:
    """
    A data class that wraps around the Youtube reply comment
    representation that is returned by the official Youtube API
    """

    def __init__(self, data_item):
        self._id = data_item["id"]
        self._text_original = data_item['snippet']['textOriginal'].strip().rstrip()
        self._author_name = data_item["snippet"]["authorDisplayName"]
        self._author_channel_url = data_item["snippet"]["authorChannelUrl"]
        self._author_channel_id = data_item["snippet"]["authorChannelId"]["value"]
        self._like_count = data_item['snippet']['likeCount']
        self._publish_date = data_item['snippet']['publishedAt']
        self._is_reply = True
        self._parent_id = data_item["snippet"]["parentId"]

    def transform_reply_to_comment(self):
        yt_comment = YtComment()
        yt_comment.set_id(self._id)
        yt_comment.set_text_original(self._text_original)
        yt_comment.set_author_name(self._author_name)
        yt_comment.set_author_channel_url(self._author_channel_url)
        yt_comment.set_author_channel_id(self._author_channel_id)
        yt_comment.set_like_count(self._like_count)
        yt_comment.set_publish_date(self._publish_date)
        yt_comment.set_is_reply(self._is_reply)
        yt_comment.set_parent_id(self._parent_id)
        return yt_comment


##################################### Elastic Search Class #####################################

class ESConnect:

    def __init__(self):
        self._es_client = Elasticsearch("http://es01:9200") #, auth=("elastic", "1234"))
        self._classifier = GenericClassifier()
        self._es_index = "yt_video"
        self._es_index_name = ""

    def _set_es_index_name(self, video_id):
        self._es_index_name = (str(self._es_index) + "_" + str(video_id)).lower()

    def store_video_data(self, video_comments_data, video_id):
        """
        Load video comments data into Elastic Search
        """
        comments = []
        for item in video_comments_data["items"]:
            comment = YtComment(item)
            comments.append(comment)
            if "replies" in item.keys(): # consider first level replies
                for reply in item["replies"]["comments"]:
                    comment_reply = YtCommentReply(reply)
                    comments.append(comment_reply.transform_reply_to_comment())

        actions = []
        self._set_es_index_name(video_id)

        for i, comment in enumerate(comments):
            source = { 'id': comment.get_id(),
                       'content': comment.get_text_original(),
                       'author_name': comment.get_author_name(),
                       'author_channel_url': comment.get_author_channel_url(),
                       'author_channel_id': comment.get_author_channel_id(),
                       'like_count': comment.get_like_count(),
                       'comment_length': len(nlp(comment.get_text_original())),
                       'publish_date': comment.get_publish_date(),
                       'is_reply': comment.get_is_reply(),
                       'parent_id': comment.get_parent_id(),
                       "spam_label": self._classifier.predict_single_comment(comment.get_text_original()),
                       "classifier": "logistic_regression"
                     }

            # detele index if existing to avoid duplicates
            try:
                self._es_client.options(ignore_status=[400,404]).indices.delete(index=self._es_index_name)
            except:
                ...

            action = {
                "_index": self._es_index_name,
                '_op_type': 'index',
                "_type": '_doc',
                "_source": source
            }
            actions.append(action)

        res = helpers.bulk(self._es_client, actions)
        return res 


    def get_spam_comments(self, video_id):
        """
        Return the spam comments found in the given video, the
        number of spam comments and the number of all comments
        """
        self._set_es_index_name(video_id)

        search_query = {"term": {
                                "spam_label.logisticregression_prediction": {
                                    "value": 1
                                    }
                                }
                        }

        search_result = self._es_client.search(index=self._es_index_name, query=search_query)
        number_spam = search_result["hits"]["total"]["value"]
        spam_comments = [ result["_source"]["content"] for result in search_result["hits"]["hits"] ]

        search_all_query = {"query": {"match_all": {}}}
        number_comments = self._es_client.count(index=self._es_index_name, body=search_all_query)["count"]

        return {"spam": spam_comments, "spam_count": number_spam, "total_count": number_comments }


##################################### Main Function #####################################

if __name__ == "__main__":
    yt = YtDataRetriever()
    es = ESConnect()
    VIDEO_ID = "kdcvyfjuKCw"
    data = yt.get_video_data(VIDEO_ID)
    res = es.store_video_data(data, VIDEO_ID)
