/**
 * Project Name: Master Control System
 *  Description: obstruction to the database.
 **/ 

var fs = require('fs');
var pg = require('pg');

var credentials = fs.readFileSync('DB_CREDENTIALS').toString().trim().split('\t');
var connectionParameters = {
	'user': credentials[0],
	'password': credentials[1],
	'host': 'localhost',
	'database': 'master_control_program',
};

function query(sql, params, onSuccess, onFailure, keepOpen){
	return pg.connect(connectionParameters, function(err, client, done) {
		if(err) {
			return console.error('Failed to connect', err);
		}
		return client.query(sql, params, function(err, result) {
			if(!keepOpen){
				done();
			}
			
			if(err){
				console.error('Error executing query', err);
				console.error(sql);
				if(onFailure){
					return onFailure(err);
				}
			}else{
				if(onSuccess){
					return onSuccess(result.rows, done);
				}
			}
		});
	});
}

module.exports = {
	connectionParameters: connectionParameters,
	regroup: function(array, keyName, valueName){
		var data = {};
		for(var i=0; i<array.length; i++){
			data[array[i][keyName]] = array[i][valueName];
		}
		return data;
	},
	
	getUsers: function(q, isAdmin, keyActive, joinDate, onSuccess, onFailure) {
		var sql =
			'SELECT ' +
			'	"isAdmin", "firstName", "lastName", "email", "joinDate", "status", ' +
			'	"nfcID" IS NOT NULL AS "keyActive" ' +
			'FROM users ' +
			'WHERE 1=1 ';

		var params = [];
		if(isAdmin !== undefined){
			params.push(isAdmin);
			sql += '	AND "isAdmin" = $' + params.length;
		}
		if(keyActive !== undefined){
			sql += '	AND "nfcID" IS ' + (keyActive ? 'NOT ': '') + 'NULL';
		}
		if(joinDate !== undefined){
			params.push(joinDate);
			sql += '	AND "joinDate" >= $' + params.length;
		}
		if(q !== undefined){
			q = '%' + q.toLowerCase() + '%';
			params.push(q);
			sql += '	AND (LOWER("firstName") LIKE $' + params.length +
				'			OR LOWER("lastName") LIKE $' + params.length +
				'			OR LOWER("email") LIKE $' + params.length +
				'		)';
		}
		
		return query(sql, params, onSuccess, onFailure);
	},
	
	// @TODO: gross. This only works in the context of WA sync'ing
	getUserByProxyID: function(proxySystem, proxyUserID, transaction) {
		var sql =
			'SELECT ' +
			'   users."userID", ' + 
			'	"isAdmin", "firstName", "lastName", "email", "joinDate", "status", ' +
			'	"nfcID" IS NOT NULL AS "keyActive" ' +
			'FROM users ' +
			'	JOIN "proxyUsers" ON users."userID" = "proxyUsers"."userID" ' +
			'	JOIN "proxySystems" ON "proxyUsers"."systemID" = "proxySystems"."systemID" ' +
			'WHERE "proxySystems".name = $1 ' +
			'	AND "proxyUsers"."proxyUserID" = $2';
			
		var extract = function(results){
			if(results.length == 1){
				transaction.updateUser(results[0]);
			}else{
				transaction.addUser();
			}
		};
		
		return query(sql, [proxySystem, proxyUserID], extract);
	},
	
	/**
	 * Requires: { firstName, lastName, email, joinDate }
	 **/
	addUser: function(user, onSuccess, onFailure){
		var sql = 'INSERT INTO users ("email", "firstName", "lastName", "joinDate") VALUES ($1, $2, $3, $4)';
		var params = [user.email, user.firstName, user.lastName, user.joinDate];
		
		return query(sql, params, onSuccess, onFailure);
	},
		
	addProxyUser: function(proxySystem, proxyUserID, user, onSuccess, onFailure){
		var sql = 'INSERT INTO users ("email", "firstName", "lastName", "joinDate") VALUES ($1, $2, $3, $4)';
		var params = [user.email, user.firstName, user.lastName, user.joinDate];
		
		return query(
			sql, params,
			function(){
				var systemSQL = 'SELECT "systemID" FROM "proxySystems" WHERE name = $1 LIMIT 1';
				var userSQL = 'SELECT "userID" FROM "users" WHERE "email" = $2 LIMIT 1';
				var sql = 'INSERT INTO "proxyUsers" ("systemID", "userID", "proxyUserID") ' +
					'VALUES ((' + systemSQL + '), (' + userSQL + '), $3)';
					
				var params = [proxySystem, user.email, proxyUserID];
				
				return query(sql, params, onSuccess, onFailure);
			},
			onFailure
		);
	},
		
	updateUser: function(user, onSuccess, onFailure){
		var sql = 'UPDATE users SET email=$1, "firstName"=$2, "lastName"=$3, "joinDate"=$4 ' +
			'WHERE "userID" = $5';
		var params = [user.email, user.firstName, user.lastName, user.joinDate, user.userID];
		
		return query(sql, params, onSuccess, onFailure);
	},

	enablePlugin: function(pluginName, onSuccess, onFailure){
		return query('UPDATE plugins SET enabled = TRUE WHERE name = $1', [pluginName], onSuccess, onFailure);
	},
	
	disablePlugin: function(pluginName, onSuccess, onFailure){			
		return query('UPDATE plugins SET enabled = FALSE WHERE name = $1', [pluginName], onSuccess, onFailure);
	},
	
	addPluginOption: function(pluginName, optionName, type, onSuccess, onFailure){
		return query(
			'SELECT "pluginID" FROM plugins WHERE name = $1',
			[pluginName],
			function(rows){
				var sql = 'INSERT INTO "pluginOptions" (name, type, ordinal, "pluginID") VALUES ($1, $2, 999, $3)';
				var params = [optionName, type, rows[0].pluginID];
				return query(sql, params, onSuccess, onFailure);
			}
		);
	},
	
	removePluginOption: function(pluginName, optionName, onSuccess, onFailure){
		return query(
			'SELECT "pluginID" FROM plugins WHERE name = $1',
			[pluginName],
			function(rows){
				var sql = 'DELETE FROM "pluginOptions" WHERE "pluginID" = $1 AND name = $2';
				var params = [rows[0].pluginID, optionName];
				return query(sql, params, onSuccess, onFailure);
			}
		);
	},
	
	registerPlugin: function(plugin, onSuccess, onFailure){
		var logAndFail = function(msg){
			console.error("Failed to register plugin (" + plugin + "): " + msg);
			if(onFailure) onFailure();
		};

		return query(
			'INSERT INTO plugins (name) VALUES ($1)',
			[plugin.name],
			function(){
				return query(
					'SELECT "pluginID" FROM plugins WHERE name = $1',
					[plugin.name],
					function(rows){
						plugin.pluginID = rows[0].pluginID;
						if(Object.keys(plugin.options).length > 0){
							var sql = 'INSERT INTO "pluginOptions" (name, type, ordinal, "pluginID") VALUES ';
							var ordinal = 0;
							var params = [];
							for(var key in plugin.options){
								sql += '($' + (ordinal*4+1) + ', $' + (ordinal*4+2) + ', $' + (ordinal*4+3) + ', $' + (ordinal*4+4) + '), ';
								params.push(key);
								params.push(plugin.options[key]);
								params.push(ordinal);
								params.push(plugin.pluginID);
								
								ordinal++;
							}
							sql = sql.substring(0, sql.length-2);
							return query(sql, params, function(){onSuccess(plugin);}, logAndFail);
						}else{
							onSuccess(plugin);
						}
					},
					logAndFail
				);
			},
			logAndFail
		);
	},
	
	registerClientPlugin: function(plugin, onSuccess, onFailure){
		this.registerPlugin(plugin, function(){
			return query(
				'SELECT "pluginID" FROM plugins WHERE name = $1',
				[plugin.name],
				function(rows){
					var pluginID = rows[0].pluginID;
					var sql = 'INSERT INTO "clientPluginOptions" (name, type, ordinal, "pluginID") VALUES ';
					var ordinal = 0;
					var params = [];
					for(var key in plugin.clientDetails['options']){
						sql += '($' + (ordinal*4+1) + ', $' + (ordinal*4+2) + ', $' + (ordinal*4+3) + ', $' + (ordinal*4+4) + '), ';
						params.push(key);
						params.push(plugin.clientDetails['options'][key]);
						params.push(ordinal);
						params.push(pluginID);
						
						ordinal++;
					}
					if(params.length > 0){
						sql = sql.substring(0, sql.length-2);
						return query(sql, params, function(){onSuccess(plugin);}, onFailure);
					}
				},
				onFailure
			);
			
		}, onFailure);
	},
	
	addProxySystem: function(systemName, onSuccess, onFailure){
		return query('INSERT INTO "proxySystems" (name) VALUES ($1)', [systemName], onSuccess, onFailure);
	},

	getPlugins: function(onSuccess, onFailure){
		return query('SELECT * FROM plugins', null, onSuccess, onFailure);
	},
	
	getPluginOptions: function(pluginName, onSuccess, onFailure){
		return this._getPluginOptions(pluginName, false, onSuccess, onFailure);
	},
	
	getOrderedPluginOptions: function(pluginName, onSuccess, onFailure){
		return this._getPluginOptions(pluginName, true, onSuccess, onFailure);
	},
	
	_getPluginOptions: function(pluginName, leaveOrdered, onSuccess, onFailure){
		var sql = 
			'SELECT ' +
			'	"pluginOptions"."name", ' +
			'	type, ' +
			'	value ' +
			'FROM plugins ' +
			'	JOIN "pluginOptions" ON plugins."pluginID" = "pluginOptions"."pluginID" ' +
			'	LEFT JOIN "pluginOptionValues" ON "pluginOptions"."pluginOptionID" = "pluginOptionValues"."pluginOptionID" ' +
			'WHERE plugins.name = $1 ' +
			'ORDER BY ordinal ';
		
		var self = this;
		var process = onSuccess;
		
		if(!leaveOrdered){
			process = function(data){
				onSuccess(self.regroup(data, 'name', 'value'));
			};
		}
		return query(sql, [pluginName], process, onFailure);
	},
	
	setPluginOption: function(pluginName, optionName, value, onSuccess, onFailure){
		// @TODO: collapse into a single query or find a better sequential execution method (async module?)
		return query(
			'SELECT "pluginID" FROM plugins WHERE name = $1',
			[pluginName],
			function(plugin){
				var pluginID = plugin[0].pluginID;
				
				return query(
					'SELECT "pluginOptionID" FROM "pluginOptions" WHERE "pluginID" = $1 AND name = $2',
					[pluginID, optionName],
					function(pluginOption){
						var optionID = pluginOption[0].pluginOptionID;
						return query(
							'SELECT value FROM "pluginOptionValues" WHERE "pluginOptionID" = $1',
							[optionID],
							function(rows){
								return query(
									'DELETE FROM "pluginOptionValues" WHERE "pluginOptionID" = $1',
									[optionID],
									function(){
										var sql = 'INSERT INTO "pluginOptionValues" ("pluginOptionID", value) VALUES ($1, $2)';
										return query(sql, [optionID, value], onSuccess, onFailure);
									},
									onFailure
								);
							},
							onFailure
						);
					},
					onFailure
				);
			},
			onFailure
		);
	},
	
	getClients: function(onSuccess, onFailure){
		var sql = 
			'SELECT ' +
			'	clients."clientID", ' + 
			'	clients.name AS "clientName", ' + 
			'	plugins.name AS "pluginName", ' + 
			'	"clientPluginOptions".name AS "optionName", ' + 
			'	"clientPluginOptions".type AS "optionType", ' + 
			'	"clientPluginOptionValues"."optionValue" AS "optionValue" ' + 
			'FROM clients ' + 
			'	LEFT JOIN "clientPluginAssociations" ON clients."clientID" = "clientPluginAssociations"."clientID" ' +
			'	LEFT JOIN "plugins" ON "clientPluginAssociations"."pluginID" = "plugins"."pluginID" ' + 
			'	LEFT JOIN "clientPluginOptions" ON "plugins"."pluginID" = "clientPluginOptions"."pluginID" ' + 
			'	LEFT JOIN "clientPluginOptionValues" ON "clientPluginOptions"."clientPluginOptionID" = "clientPluginOptionValues"."clientPluginOptionID" ' + 
			'		AND clients."clientID" = "clientPluginOptionValues"."clientID" ';
		return query(
			sql,
			null,
			function(rows){
				var clients = [];
				var currentClient = null;
				var currentPlugin = null;
				for(var i=0; i<rows.length; i++){
					if(!currentClient || currentClient.clientID != rows[i].clientID){
						currentClient = {
							'clientID' : rows[i].clientID,
							'name' : rows[i].clientName,
							'plugins': {},
						};
						clients.push(currentClient);
						
						currentPlugin = null;
					}
					if(rows[i].pluginName){
						if(!currentPlugin || currentPlugin.name != rows[i].pluginName){
							currentPlugin = {
								'name': rows[i].pluginName,
								'options': [],
							};
							currentClient['plugins'][currentPlugin.name] = currentPlugin;
						}
					}
					if(rows[i].optionName){
						currentPlugin.options.push({
							'name': rows[i].optionName,
							'type': rows[i].optionType,
							'value': rows[i].optionValue,
						});
					}
				}
				onSuccess(clients);
			},
			onFailure)
		;
	},
	
	addClient: function(name, onSuccess, onFailure){
		var sql = 'INSERT INTO clients (name) VALUES ($1)';
		return query(sql, [name], onSuccess, onFailure);
	},
	
	associateClientPlugin: function(clientID, pluginID, onSuccess, onFailure){
		var sql = 'INSERT INTO "clientPluginAssociations" ("clientID", "pluginID") VALUES ($1, $2)';
		return query(sql, [clientID, pluginID], onSuccess, onFailure);
	},
};
