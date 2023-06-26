# Flask-shortlink

用Flask实现的短链接api

## Example

POST /

```
{"token":"123","action":0,"link":"https://example.com","expire":86400}
```

Response be like

```
{"status":"success","link":"https://example.org/14514","expire":86400}
```

or

```
{"status":"error","message":"some message"}
```