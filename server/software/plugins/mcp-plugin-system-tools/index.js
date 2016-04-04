var backend = require('../../backend.js');
var child_process = require('child_process');
var tmp = require('tmp');
var fs = require('fs');

var runningProcs = {};

module.exports = {
	name: 'System Tools',
	options: {
		'Log line limit': 'number'
	},
	actions: {
		'Download log': function(session){
			backend.getPluginOptions(module.exports.name, function(settings){
				tmp.file(function(err, tmpFilePath, fd, cleanupCallback){
					var filename = encodeURIComponent(tmpFilePath.substring(tmpFilePath.lastIndexOf('/')+1));
					session.response.send({ 'url': '/plugins/' + encodeURIComponent(module.exports.name) + '/handler?f=' + filename });
					
					var args = '-u master-control-program --no-pager'.split(' ');
					if(settings['Log line limit']){
						args.push('-n');
						args.push(settings['Log line limit']);
					}
					var proc = child_process.spawn('journalctl', args);
					runningProcs[filename] = {
						'proc' : proc,
						'running': true,
						'cleanup': cleanupCallback,
					};
					proc.stdout.on('data', function(data) {
						fs.appendFile(tmpFilePath, data);
					});
					proc.stdout.on('end', function(data){
						backend.log('Systemd Log Generated');
						backend.debug(filename);
						runningProcs[filename].running = false;
						fs.close(fd);
					});
					proc.stdin.end();
				});
			});
		},
		'Restart MCP': function(session){
			backend.log('Server will now restart');
			child_process.exec('systemctl restart master-control-program');
		},
		'Reboot server': function(session){
			backend.log('System will now reboot');
			child_process.exec('reboot');
		},
		'Shutdown server': function(session){
			backend.log('System will now power off');
			child_process.exec('poweroff');
		},
	},

	onInstall: function(){},
	onUninstall: function(){},
	onEnable: function(){},
	onDisable: function(){},
	
	handleRequest: function(request, response){
		var f = request.params.f;
		if(!runningProcs[f]){
			response.send(404, 'File not found :(');
			response.end();
		}else if(runningProcs[f].running){
			response.write('<html><head><meta http-equiv="refresh" content="10" /></head><body><pre><h1>[' + (new Date()) + '] Retreiving log...</h1></pre></body></html>');
			response.end();
		}else{
			fs.readFile('/tmp/' + f, 'utf8', function(err, file) {
				if (err) {
					backend.error('Systemd log failed :(');
					response.send(500);
				}else{
					response.write(file);
					runningProcs[f].cleanup();
					delete runningProcs[f];
				}
				response.end();
			});
		}
	},
};