from pymongo import MongoReplicaSetClient
import pymongo
from bson import ObjectId
import gridfs

def get_connection(host, port, user, password, auth=True):
    try:
        con = MongoReplicaSetClient(host, port, replicaSet="forest")
    except pymongo.errors.ConfigurationError, pymongo.errors.ConnectionFailure:
        con = pymongo.MongoClient(host, port)
    if auth:
        con.admin.authenticate(user, password)
    return con

CONNECTION = get_connection("127.0.0.1", 27017, "admin", "password")
DB = CONNECTION['files']
FS = gridfs.GridFS(DB)

def get_species_and_filename(uri):
    parts = filter(None, uri.split("/"))
    if len(parts) < 2:
        return "", ""
    specie = parts[1]
    filename = "/".join(parts[2:])
    return specie, filename

def application(env, start_response):
    uri = env['PATH_INFO']
    species, filename = get_species_and_filename(uri)
    if not all([species, filename]):
        start_response('404 NOT FOUND', [('Content-Type', 'text/plain')])
        return []    
    print species, filename
    for grid_file in FS.find({"filename": filename, "species": species}):
        start_response('200 OK', [('Content-Type', str(grid_file.content_type))])
        return [grid_file.read()]
    start_response('404 NOT FOUND', [('Content-Type', 'text/plain')])
    return []
    