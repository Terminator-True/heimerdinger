from pymongo import MongoClient


def get_db(mongo_uri: str = None):
    if mongo_uri is None:
        mongo_uri = "mongodb://localhost:27017/heimerdinger"
    client = MongoClient(mongo_uri)
    return client.get_default_database()
