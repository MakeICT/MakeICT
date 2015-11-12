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

function query(sql, params, onSuccess, onError, keepOpen){
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
				if(onError){
					return onError(err);
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
	
	/**
	 * Requires: { firstName, lastName, email, joinDate }
	 **/
	addUser: function(user, onSuccess, onFailure){
		var sql = 'INSERT INTO users ("email", "firstName", "lastName", "joinDate") VALUES ($1, $2, $3, $4)';
		var params = [user.email, user.firstName, user.lastName, user.joinDate];
		
		return query(sql, params, onSuccess, onFailure);
	},
		
	enablePlugin: function(pluginName, onSuccess, onFailure){
		return query('UPDATE plugins SET enabled = TRUE WHERE name = $1', [pluginName], onSuccess, onFailure);
	},
	
	disablePlugin: function(pluginName, onSuccess, onFailure){			
		return query('UPDATE plugins SET enabled = FALSE WHERE name = $1', [pluginName], onSuccess, onFailure);
	},
	
	registerPlugin: function(plugin, onSuccess, onError){
		return query(
			'INSERT INTO plugins (name) VALUES ($1)',
			[plugin.name],
			function(){
				return query(
					'SELECT "pluginID" FROM plugins WHERE name = $1',
					[plugin.name],
					function(rows){
						var pluginID = rows[0].pluginID;
						var sql = 'INSERT INTO "pluginOptions" (name, type, ordinal, "pluginID") VALUES ';
						var ordinal = 0;
						var params = [];
						for(var key in plugin.options){
							sql += '($' + (ordinal*4+1) + ', $' + (ordinal*4+2) + ', $' + (ordinal*4+3) + ', $' + (ordinal*4+4) + '), ';
							params.push(key);
							params.push(plugin.options[key]);
							params.push(ordinal);
							params.push(pluginID);
							
							ordinal++;
						}
						if(params.length > 0){
							sql = sql.substring(0, sql.length-2);
							return query(sql, params, onSuccess, onError);
						}
					},
					onError
				);
			},
			onError
		);
	},

	getPlugins: function(onSuccess, onFailure){
		return query('SELECT * FROM plugins', null, onSuccess, onFailure);
	},
	
	getPluginOptions: function(pluginName, onSuccess, onFailure){
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
		var preProcess = function(data){
			onSuccess(self.regroup(data, 'name', 'value'));
		};
		
		return query(sql, [pluginName], onSuccess, onFailure);
	},
	
	setPluginOption: function(pluginName, optionName, value, onSuccess, onError){
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
										return query(sql, [optionID, value], onSuccess, onError);
									},
									onError
								);
							},
							onError
						);
					},
					onError
				);
			},
			onError
		);
	}
};