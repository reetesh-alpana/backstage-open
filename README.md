# The Backstage Web Framework

The Backstage Web Framework allows to describe your RESTful service in the form of an XML. The instructions that are mentioned in the XML are in the form of a sequence of mediators that get executed one by one. Backstage is completely written in Python ( 2.7 ).

# Dependencies

- lxml - The library that is used to parse the XML work file 
- gunicorn - Backstage can be started as a simple WSGI server and a Gunicorn server with multiple instances

# Installation

Backstage is available on PyPi - < Link >. It can be installed using pip, easy install or by running setup.py install.

# Introduction

Backstage takes an xml file or path containing xmls which have various instrcutions on how to handle a request.

### An Example 

```xml
<?xml version="1.0" encoding="UTF-8"?>
<apis>
   <api name="hello" context="^greet/$">
      <resource method="GET">
         <inSequence>
            <log category="info" value="Dummy InSequence does not do anything !!" />
            <processresponse />
         </inSequence>
         <outSequence>
            <log category="info" value="Dummy OutSequence Starts" />
            <response value="Hello World !!" status_code="200" status_message="Ok">
               <header name="content-type" value="text/plain" />
            </response>
            <log category="info" value="Hello World Done !! Great" />
         </outSequence>
         <faultSequence>
            <log category="error" handler="" format="" value="There is an error in the request " />
         </faultSequence>
      </resource>
   </api>
</apis>
```

Looks too much ? We will discuss that in detail. This is available in the examples directory as well. 

### Running the server

```console
$ backstage_serve simple <xml-file-or-directory> <host> <port> --settings=<path-to-the-settings-file>
```

- backstage_serve is the entry point that gets created when this package is installed
- simple refers to the type of sever. 'simple' being the basic wsgi server, the other option is to use gunicorn which is discussed later


### Running the example

The XML mentioned above is an example of a RESTful service. Lets call it first using curl to see how it responds, then we will proceed into the details.

```console
$ curl 127.0.0.1:8011/greet

Hello World !!
```
And the console output on the backstage_serve end should look like this

```console
INFO:backstage:Sequence returning for GET method, /greet url path 
INFO:root:Sequence being called Log 
INFO:backstage:Dummy InSequence does not do anything !!
INFO:root:Sequence being called ProcessResponseMediator 
INFO:backstage:Sequence returning for GET method, /greet url path 
INFO:root:Out Sequence being called Log 
INFO:backstage:Dummy OutSequence Starts
INFO:root:Out Sequence being called ResponseMediator 
INFO:root:Out Sequence being called Log 
INFO:backstage:Hello World Done !! Great
127.0.0.1 - - [05/Sep/2017 17:49:24] "GET /greet HTTP/1.1" 200 14
```

# Basics 

The XML contains several tags, we will go into each tag in this section. Each of the tags are mapped into a Python class with a 'mediate' function, while process any tag the backstage server will run the mediate function. 

The user has the ability to customize the tags by adding a new python class with the mediate function. We have an example for this later on.

<h3>apis</h3>
Does not perform any activity apart from being the root tag for all XML files that will be processed by backstage. It has to contain a collection of 'api' tags.

<h3>api</h3>
Describes the api. It must contain the 'name' and 'context' attributes. 
- name - The name by which the API can be identified
- context - The URI to which the request must conform to. In this example in has to be 'greet/'. This follows the matching patterns that Django uses.

If the wrong API is accessed then a 404 is thrown.

```console
$ curl 127.0.0.1:8011/greets
URI /greets not found in defined API's
```

<h3>resource</h3>
Refers to GET, POST, DELETE, PUT or PATCH. In this example it has to be a GET request. If any request other than GET is made then a 405 Method Not Supported error is thrown.

```console
$ curl -X POST -d {} 127.0.0.1:8011/greet -v
*   Trying 127.0.0.1...
* Connected to 127.0.0.1 (127.0.0.1) port 8011 (#0)
> POST /greet HTTP/1.1
> Host: 127.0.0.1:8011
> User-Agent: curl/7.43.0
> Accept: */*
> Content-Length: 2
> Content-Type: application/x-www-form-urlencoded
> 
* upload completely sent off: 2 out of 2 bytes
* HTTP 1.0, assume close after body
< HTTP/1.0 405 Method Not Supported
< Date: Tue, 05 Sep 2017 13:09:19 GMT
< Server: WSGIServer/0.1 Python/2.7.10
< Content-type: text/plain
< Content-Length: 0
< 
* Closing connection 0
```

<h3>insequence</h3>
Once the above requirements are met the tags in insequence are executed sequentially

<h3>log</h3>
Just logs based on the information presesnt in the tag.

```console
INFO:backstage:Dummy InSequence does not do anything !!
```

<h3>processresponse</h3>
If this tag is encountered at any time the insequence is considered to be done and the outsequence is called.

<h3>outsequence</h3>
Once the request is completely dealt with the outsequence is called. This in turn can use different tags etc as shown in the example.

<h3>response & header</h3>
Response should be used in the outsequence as a custom response can be created based on the requirements. It can have a 'value', 'status_code' and 'status_message' as descibed in the example below. 

The Header tag contain the 'name' and 'value' tags to descibe any response headers that needs to be returned.

```console
<response value="Hello World !!" status_code="200" status_message="Ok">
  <header name="content-type" value="text/plain" />
</response>
```

<h3>faultsequence</h3>
In case of an error while processing the request this sequence will be called.

