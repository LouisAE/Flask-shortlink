from flask import Flask,render_template,Response,request,redirect
from flask_restful import Resource, Api,reqparse
from requests import get
import redis
from json import loads
import os
from hashlib import md5
from random import randint


app = Flask(__name__)
api = Api(app)

#http状态码对应的错误信息
httpErrorMsg = {
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    500: "Internal Error"
}

class ShortLink(Resource):
    def get(self,key:str):
        dataBase = redis.from_url(os.environ.get("DB_URL"))
        link = dataBase.get(key)
        
        if link != None and dataBase.type(key) == b'string':
            return redirect(link.decode("utf-8"))
        else:
            return http_error(404,"The link cannot be found in the database")
    def post(self,key:str):
        return http_error(405)
    
api.add_resource(ShortLink, '/<key>')
    
class ShortLinkRoot(Resource):
    def get(self):
        return http_error(404)
    def post(self):
        parser = reqparse.RequestParser() #准备读取数据
        parser.add_argument("token", type=str, required=True)
        parser.add_argument("action",type=int, required=True)
        parser.add_argument("link",type=str)
        parser.add_argument("key",type=str)
        parser.add_argument("expire",type=int)#单位:天
        args = parser.parse_args()
        
        dataBase = redis.from_url(os.environ.get("DB_URL"))
        
        if not dataBase.sismember("tokens",args["token"]):#鉴权
            return http_error(403,"Token invalid")
        if args["action"] == 0:
            md = md5()
            try:
                md.update(args["link"].encode())
            except AttributeError:#客户端可能没有提供链接
                return http_error(400,"Link not provided")
            rdint = randint(0,31-5)
            key = md.hexdigest()[rdint:rdint+5]#从哈希散列中随机取5位作为key
            dataBase.set(key,args["link"])
            
            responseJson = {"status":"success"}
            responseJson["link"] = os.environ.get("DOMAIN")+key
            responseJson["expire"] = 0
            
            if args["expire"] != None and args["expire"] != 0:#若过期时间存在且不为永久则设置
                dataBase.expire(key,args["expire"]*86400)
                responseJson["expire"] = args["expire"]
            return responseJson,201
        
        if args["action"] == 1:
            if args["key"] == None:
                return http_error(400,"Key not provided")
            if dataBase.exists(args["key"]) and dataBase.type(args["key"]) == b'string':
                dataBase.delete(args["key"])
            else:
                return http_error(404,"The link cannot be found in the database")
            return {"status":"success","message":"Link deleted"},200
api.add_resource(ShortLinkRoot, '/')

        
#http错误处理，通过用户代理判断应该返回什么错误内容
def http_error(error_code:int,msg=None):
    responseJson = {"status":"error"}
    if msg != None:#添加错误信息
        responseJson["message"] = msg
    else:
        responseJson["message"] = httpErrorMsg[error_code]

    if str(request.user_agent).find("Mozilla") != -1:
        errorimg = get("https://http.cat/"+str(error_code)).content
        return Response(errorimg,mimetype="image/jpeg")#浏览器则返回图片
    else:
        return responseJson,error_code #否则返回错误信息