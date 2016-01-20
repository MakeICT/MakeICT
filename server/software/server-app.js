var restify = require('restify');
var backend = require('./backend.js');

var doneLoading = false;


var server = restify.createServer({
//	certificate: fs.readFileSync('cert.pem'),
//	key: fs.readFileSync('key.pem'),
	name: 'master-control-program',
});
var io = require('socket.io').listen(server.server);

server.use(restify.fullResponse());
server.use(restify.queryParser());
server.use(restify.bodyParser());

/**
 * #############
 * # REST
 * #############
 **/
server.get('/users', function (request, response, next) {
	backend.getUsers(request.params.q, request.params.isAdmin, request.params.keyActive, request.params.joinDate, function(users){
		response.send(users);
	});
	
	return next();
});

/**
 * Sends empty response on success
 * Sends a message 
 **/
server.post('/users', function (request, response, next) {
	request.params.joinDate = parseInt(Date.parse(request.params.joinDate) / 1000);
	backend.addUser(
		request.params,
		function(result){
			response.send();
		},
		function(error){
			response.send(error.detail);
		}
	);
	
	return next();
});

/**
 * Plugins
 **/
server.get('/plugins', function (request, response, next) {
	response.send(backend.getPlugins());
	return next();
});

server.put('/plugins/:plugin/enabled', function (request, response, next) {
	var task = request.params.value ? backend.enablePlugin : backend.disablePlugin;
	var plugin = backend.getPluginByName(request.params.plugin);
	task(
		plugin.name,
		function(){
			if(request.params.value){
				plugin.onEnable();
			}else{
				plugin.onDisable();
			}
			response.send();
		},
		function(error){
			response.send(error.detail);
		}
	);
	
	return next();
});

server.get('/plugins/:name/options', function (request, response, next) {
	backend.getOrderedPluginOptions(request.params.name, function(options){
		// sending the plugin name is back because of a weird front-end scoping issue
		// also, options here are ordered, so don't make a dict out of them.
		response.send({
			'plugin': request.params.name,
			'options': options,
		});
	});
	
	return next();
});

server.put('/plugins/:plugin/options/:option', function (request, response, next) {
	backend.setPluginOption(
		request.params.plugin, request.params.option, request.params.value,
		function(){
			response.send();
		},
		function(error){
			response.send(error.detail);
		}
	);
	
	return next();
});

server.post('/plugins/:plugin/actions/:action', function (request, response, next) {
	try{
		backend.getPluginByName(request.params.plugin).actions[request.params.action]();
	}catch(exc){
		console.log(exc);
	}
	
	return next();
});


/**
 * Clients
 **/
server.get('/clients', function(request, response, next) {
	response.send(backend.getClients());
	
	return next();
});

server.post('/clients/:clientID/plugins/:pluginName', function (request, response, next) {
	backend.associateClientPlugin(request.params.clientID, request.params.pluginName, function(){ response.send(); });
	return next();
});

server.post('/clients/:clientID/plugins/:pluginName/actions/:action', function (request, response, next) {
	var client = backend.getClientByID(request.params.clientID);
	var plugin = backend.getPluginByName(request.params.pluginName);
	var action = plugin['clientDetails']['actions'][request.params.action];
	
	action(client, function(){ response.send(); });
	
	return next();
});

server.put('/clients/:clientID/plugins/:pluginName', function (request, response, next) {
	backend.setClientPluginOption(
		request.params.clientID, request.params.pluginName, request.body.option, request.body.value,
		function(){
			response.send();
		},
		function(error){
			response.send(error.detail);
		}
	);

	return next();
});

/**
 * #############
 * # Stuff
 * #############
 **/
// Serve static files for the web client
server.get(/.*/, restify.serveStatic({
	directory: 'public/',
	default: 'index.html'
}));

io.sockets.on('connection', function (socket) {
	console.log("CONNECT: " + socket.id);
	
	socket.on('disconnect', function (reason) {
		console.log("DISCONNECT (" + reason + "): " + socket.id);
	});
});


server.listen(3000, function () {
	console.log('%s listening at %s', server.name, server.url);
});

