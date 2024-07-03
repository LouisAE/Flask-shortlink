from hashlib import md5
from random import randint
from flask import Flask,Response,request,redirect
from flask_restful import Resource,Api,reqparse
from requests import get
import redis
import os
import time



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

# 计算key:md5散列后取随机五位
def calc_key(content:str) -> str:
    md = md5()
    md.update(bytes(content + str(int(time.time()))))
    rdint = randint(0, 31 - 5)
    return md.hexdigest()[rdint:rdint + 5]


class ShortLink(Resource):
    def get(self,key:str):
        dataBase = redis.from_url(os.environ.get("DB_URL"))
        if dataBase.exists(key):
            if not dataBase.type(key) == b'string':
                return http_error(403)
            link = dataBase.get(key)
            return redirect(link.decode("utf-8"))
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
        parser.add_argument("expire",type=int)#单位:秒
        parser.add_argument("content",type=str) # 静态内容
        args = parser.parse_args()

        dataBase = redis.from_url(os.environ.get("DB_URL"))

        # 鉴权
        if not dataBase.sismember("tokens",args["token"]):
            return http_error(403,"Token invalid")
        
        # add
        if int(args["action"]) == 0:
            try:
               key = calc_key(args["link"])
            except AttributeError:#客户端可能没有提供链接
                return http_error(400,"Link not provided")
            dataBase.set(key,args["link"])

            responseJson = {"status":"success"}
            responseJson["link"] = os.environ.get("DOMAIN")+key
            responseJson["expire"] = 0

            if args["expire"] is not None and int(args["expire"]) != 0:#若过期时间存在且不为永久则设置
                dataBase.expire(key,int(args["expire"]))
                responseJson["expire"] = args["expire"]

            return responseJson,201

        # delete
        elif int(args["action"]) == 1:
            if args["key"] is None:
                return http_error(400,"Key not provided")
            if dataBase.exists(args["key"]) and dataBase.type(args["key"]) == b'string':
                dataBase.delete(args["key"])
            else:
                return http_error(404,"The link cannot be found in the database")
            return {"status":"success","message":"Link deleted"},200
        
        # add static
        elif int(args["action"]) == 2:
            try:
                key = calc_key(args["content"])
            except AttributeError:
                return http_error(400, "Content not provided")
            
            dataBase.hset("static",key,args["content"])

            responseJson = {"status":"success"}
            responseJson["link"] = os.environ.get("DOMAIN") + f"static/{key}"
            responseJson["expire"] = 0

            if args["expire"] is not None and int(args["expire"]) != 0:
                dataBase.hexpire("static",key,int(args["expire"]))
                responseJson["expire"] = args["expire"]
            return responseJson,201
        
        else:
            return http_error(400, "Unknown action")
            
api.add_resource(ShortLinkRoot, '/')

class staticContent(Resource):
    def get(self,key:str):
        dataBase = redis.from_url(os.environ.get("DB_URL"))
        content = dataBase.hget("static",key)

        if content is not None:
            return Response(content.decode("utf-8"))
        else:
            return http_error(404,"The link cannot be found in the database")
    def post(self,key:str):
        return http_error(405)

api.add_resource(staticContent,'/static/<key>')        
#http错误处理，通过用户代理判断应该返回什么错误内容
def http_error(error_code:int,msg=None):
    responseJson = {"status":"error"}
    if msg is not None:#添加错误信息
        responseJson["message"] = msg
    else:
        responseJson["message"] = httpErrorMsg[error_code]

    if str(request.user_agent).find("Mozilla") != -1:
        errorimg = get("https://http.cat/"+str(error_code)).content
        return Response(errorimg,status=error_code,mimetype="image/jpeg")#浏览器则返回图片
    return responseJson,error_code #否则返回错误信息
