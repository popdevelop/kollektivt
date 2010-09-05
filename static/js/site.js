String.prototype.ts2rel = function() {
    var d = new Date(this).getTime();
    var now = new Date().getTime();
    var diff = (d - now)/1000;
    if(diff < 60) {
        return "now";
    }
    return Math.floor(diff / 60) + " min";
};

var Config =  {
    server: '',
    pollInterval: 2000
};

var Cmd = {
    send: function(cmd, params) {
        if( !(cmd in API) ) {
            throw("[API] Invalid command");
        }
        if( typeof(params) != 'object') {
            throw("[API] Invalid parameters");
        }
        params.url = Config.server + "/" + API[cmd];
        $.jsonp(params);
    }
};

var API = {
    getRoutes: 'lines',
    getVehicles: 'vehicles'
};

var GMap = {
    $canvas: false,
    _options: {
        scrollwheel: false,
        zoom: 14,
        mapTypeId: google.maps.MapTypeId.ROADMAP,
        lat: 55.609384,
        lon: 12.996826
    },
    _markers: [],
    _bounds: false,
    _info: false,
    init: function(map_id) {
        GMap.$canvas = $(map_id);
        if(!GMap.$canvas) {
            throw("[GMap init] Canvas not found");
        }
        GMap._options.center = new google.maps.LatLng(GMap._options.lat, GMap._options.lon);
        GMap.map = new google.maps.Map(GMap.$canvas.get(0), GMap._options);
    },
    set: function(options) {
        if(typeof(options) != 'object') {
            throw("[GMap set] Invalid options");
        }
        $.extend(GMap._options, options);
        GMap._options.center = new google.maps.LatLng(GMap._options.lat, GMap._options.lon);
        GMap.map.setCenter(GMap._options.center);
        GMap.map.setZoom(GMap._options.zoom);
    },
    addMarkers: function(positions) {
        GMap._bounds = new google.maps.LatLngBounds();
        for(var i in positions) {
            var p = positions[i];
            var lonlat = new google.maps.LatLng(p.lat, p.lon);
            GMap._markers[p.key] = new google.maps.Marker({
                position: lonlat, 
                map: GMap.map, 
                title: p.name
            });
            GMap._bounds.extend(lonlat);
            /*google.maps.event.addListener(GMap._markers[p.key], "click", function() {
                alert("hej");
            });*/
        }
    },
    clearMarkers: function() {
        if(GMap._info) {
            GMap._info.close();
        }
        for (var i in GMap._markers) {
            GMap._markers[i].setMap(null);
        }
        GMap._markers.length = 0;
    },
    autoZoom: function() {
        GMap.map.fitBounds(GMap._bounds);
        GMap.map.setCenter(GMap._bounds.getCenter());
    },
    displayInfo: function(marker_id, info) {
        if(GMap._info) {
            GMap._info.close();
        }
        marker = GMap._markers[marker_id];
        if(!marker) {
            throw("[GMap displayInfo] Invalid marker");
        }
        GMap._info = new google.maps.InfoWindow(
        {
            content: info,
            position: marker.position
        });
        GMap._info.open(GMap.map);
    }
};

var TimeTable = {
    $canvas: false,
    $result: false,
    init: function(tbl_id) {
        TimeTable.$canvas = $(tbl_id);
        if(!TimeTable.$canvas) {
            throw("[TimeTable init] Failed to init");
        }
        TimeTable.$result = $('<table>');
        TimeTable.$canvas.append(TimeTable.$result);
    },
    fetch: function(station_id) {
        Cmd.send('stationResult', {
            data: {s: station_id},
            success: TimeTable.display,
            callbackParameter: 'callback'
        });
    },
    display: function(json) {
        TimeTable.$result.html($('#lineItem').tmpl(json));
    }
};

var LineColors = {
    1: "#bb60d2",
    2: "#cf4d6a",
    3: "#24b1cf",
    4: "#cf1d1d",
    5: "#743eab",
    6: "#38aaab",
    7: "#ab493c",
    8: "#d2da00"
};

function Route(route) {
    var self = this;
    self._coords  = route.coordinates;
    //self._stops   = route.stations;
    if(self._coords.length > 0) {
        var coords = [];
        for(var i in self._coords) {
            coords.push(new google.maps.LatLng(self._coords[i].lat, self._coords[i].lon));
        }
        var color = (route.name in LineColors) ? LineColors[route.name] : "#000";
        self._path = new google.maps.Polyline(
            {
                path: coords, 
                strokeColor: color,
                strokeOpacity: 1,
                strokeWeight: 5
            });
        self._path.setMap(GMap.map);
        //GMap.addMarkers(self._stops);
        //GMap.autoZoom();
    }

    self.show = function() {
        self._path.setMap(GMap.map);
    }

    self.hide = function() {
        self._path.setMap(null);
    }
};

var Traffic = {
    _routes: [],
    _timer: false,
    _vehicles: {},
    init: function() {
        $(document).bind("Server.error", Traffic.stopTracking);
    },
    getRoutes: function() {
        //Fetch routes
        Cmd.send('getRoutes', {
            callbackParameter: "callback",
            timeout: 5000,
            success: function(json){
                Traffic._routes = [];
                var html;
                for(var i in json) {
                    var r = new Route(json[i]);
                    Traffic._routes.push(r);
                    json[i].route = r;
                    $("#toolbar > ul").append($("#stationItem").tmpl(json[i]));
                }
                Traffic.startTracking();
            },
            error: function(){
                console.log("Error");
                $(document).trigger("Server.error")
            }
        });
    },
    startTracking: function() {
        //Start tracking of vehicles
        Traffic._timer = setTimeout(Traffic._fetch, 0);
    },
    stopTracking: function() {
        clearTimeout(Traffic._timer);
        for(var i in Traffic._vehicles) {
            Traffic._vehicles[i].stop();
        }
    },
    _fetch: function() {
        Cmd.send('getVehicles', {
            callbackParameter: "callback",
            timeout: 10000,
            success: Traffic._update,
            error: function() {
                console.log("error");
                $(document).trigger("Server.error");
            }
        });
    },
    _update: function(json) {
        // Reload timer
        Traffic._timer = setTimeout(Traffic._fetch, Config.pollInterval);

        var keys = {};
        GMap._bounds = new google.maps.LatLngBounds();
        //Update or create new items
        for(var i in json) {
            var v = json[i];
            var pos = {lat: v.lat, lon: v.lon, line: v.line};
            keys[v.id] = true;
            if(v.id in Traffic._vehicles) {
                Traffic._vehicles[v.id].setPosition(pos);
            } else {
                Traffic._vehicles[v.id] = new Vehicle(pos);
                Traffic._vehicles[v.id].animate();
            }
            GMap._bounds.extend(new google.maps.LatLng(v.lat, v.lon));
        }
        //GMap.autoZoom();
        //Remove orphan items
        for(var i in Traffic._vehicles) {
            if(!(i in keys)) {
                Traffic._vehicles[i].remove();
                delete Traffic._vehicles[i];
            }
        }
    },
    hideType: function(type, val) {
        for(var i in Traffic._vehicles) {
            var v = Traffic._vehicles[i];
            if(v[type] == val) {
                v.hide();
            }
        }
    },
    showType: function(type, val) {
        for(var i in Traffic._vehicles) {
            var v = Traffic._vehicles[i];
            if(v[type] == val) {
                v.show();
            }
        }
    }

};

function Vehicle(opts) {
    var self = this;
    self.line = opts.line;
    self._timer = false;
    self._pos = {lat: opts.lat, lon: opts.lon};
    self._to  = self._pos;
    self._dx = 0;
    self._dy = 0;

    self._marker = new google.maps.Marker({
        position: new google.maps.LatLng(opts.lat, opts.lon),
        map: GMap.map,
        title: "tempo"
    });

    this.setPosition = function(pos) {
        self._pos = self._to;
        self._to = pos;
        self._dx = pos.lat - self._pos.lat;
        self._dy = pos.lon - self._pos.lon;
    };

    this.animate = function() {
        self._timer = setInterval(self.next, 200);
    };
    this.stop = function() {
        clearInterval(self._timer);
    }
    this.next = function() {
        // Calculate new position
//        if(self._dx === 0 && self._dy === 0) { return; }
        self._pos.lat += self._dx*0.1; 
        self._pos.lon += self._dy*0.1;

        //Threshold XXX: really useful?
        if(Math.abs(self._pos.lat - self._to.lat) < 0.000000001) {   
            self._dx = 0;
            self._pos.lat = self._to.lat;
        }
        if(Math.abs(self._pos.lon - self._to.lon) < 0.000000001) {   
            self._dy = 0;
            self._pos.lon = self._to.lon;
        }

        var pos = new google.maps.LatLng(self._pos.lat, self._pos.lon);
        self._marker.setPosition(pos);
    };
    this.remove = function() {
        self.stop();
        self.hide();
    }

    this.hide = function() {
        self._marker.setMap(null);
        clearTimeout(self._timer);
    }
    this.show = function() {
        self._marker.setMap(GMap.map);
        self._timer = setInterval(self.next, 200);
    }
};


var ErrorHandler = {
    $popup: false,
    $shade: false,
    init: function() {
        // Create popup
        ErrorHandler.$shade = $("<div>")
            .hide()
            .attr('id', 'shade')
            .appendTo('body');
        ErrorHandler.$popup = $("<div>")
            .hide()
            .attr('id', 'errorPopup')
            .html("Ooops! Server is sad :(<span>reload to try again</span>")
            .appendTo('body');
        $(document).bind("Server.error", function() {
            ErrorHandler.$popup.show();
            ErrorHandler.$shade.show();
        });
    }
};


var timer = false;

$(document).ready(function() {
    GMap.init('#map_canvas');
    Traffic.getRoutes();
    ErrorHandler.init();
    $("#toolbar > ul > li > input").live("click", function(e) {
        var item = $.tmplItem(e.target);
        var enabled = (e.target.value == "on");
        if(enabled) {
            item.data.route.show();
            Traffic.showType('line', item.data.name);
        }
        else {
            item.data.route.hide();
            Traffic.hideType('line', item.data.name);
        }
    });
//    Route.init();
//    TimeTable.init('#timetable');
});
