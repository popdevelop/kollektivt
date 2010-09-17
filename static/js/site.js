/*
 * kollektivt.se
 * 
 * Author:
 *   popdevelop.com
 *
 * Description:
 *   Provides the logic for fetching vehicle coordinates and plotting them on
 *   the map. 
 * 
 * Requires:
 *   - jQuery
 *   - jQuery JSONP Plugin
 *   - jQuery Templating plugin
 *   - Google Maps V3 javascript API
 */


/* Misc configuration options */
var Config =  {
    server: '',
    pollInterval: 2000,
    animate: true
};


/* Sends an API command to the server */
var Cmd = (function() {
    /* Available server API methods */
    var API = {
        getRoutes: 'lines',
        getVehicles: 'vehicles'
    };

    return {
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
})();

/* Get a color according to a key */
var Color = (function(){
    var _colorBank = [
        "#bb60d2",
        "#cf4d6a",
        "#24b1cf",
        "#cf1d1d",
        "#743eab",
        "#38aaab",
        "#ab493c",
        "#d2da00"
        ],
        _currentIdx = 0,
        _keyMap = {};
    return {
        get: function(key) {
            if(key in _keyMap) {
                if(_keyMap.hasOwnProperty(key)) {
                    return _keyMap[key];
                }
            }
            var newColor = _colorBank[(_currentIdx++)%(_colorBank.length-1)];
            _keyMap[key] = newColor;
            return newColor;
        }
    };
})();

/* Simple object for handling Google map */
var GMap = (function() {
    var _$canvas = false,
        _options = {
            scrollwheel: false,
            zoom: 13,
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            lat: 55.588047,
            lon: 13.000946
        };
        
    return {
        init: function(map_id) {
            _$canvas = $(map_id);
            if(!_$canvas) {
                throw("[GMap init] Canvas not found");
            }
            _options.center = new google.maps.LatLng(_options.lat, _options.lon);
            //Set public attributes
            this.bounds = new google.maps.LatLngBounds();
            this.map = new google.maps.Map(_$canvas.get(0), _options);
        },
        autoZoom: function() {
            this.map.fitBounds(this.bounds);
            this.map.setCenter(this.bounds.getCenter());
        }
    };
})();

/*
 * Classes
 */
function Route(route) {
    var self = this;
    self._coords  = route.coordinates;
    if(self._coords.length > 0) {
        var coords = [];
        for(var i in self._coords) {
            if(self._coords.hasOwnProperty(i)) {
                coords.push(new google.maps.LatLng(self._coords[i].lat, self._coords[i].lon));
            }
        }
        var color = Color.get(route.name);
        self._path = new google.maps.Polyline(
            {
                path: coords, 
                strokeColor: color,
                strokeOpacity: 1,
                strokeWeight: 5
            });
        self._path.setMap(GMap.map);
        //GMap.autoZoom();
    }

    self.show = function() {
        self._path.setMap(GMap.map);
    };

    self.hide = function() {
        self._path.setMap(null);
    };
}

function Vehicle(opts) {
    var self = this;
    self.line = opts.line;
    self._timer = false;
    self._pos = {lat: opts.lat, lon: opts.lon};
    self._version = opts.version || false;
    self._deviation = 0;
    self._to  = self._pos;
    self._dx = 0;
    self._dy = 0;


    self._marker = new google.maps.Marker({
        position: new google.maps.LatLng(opts.lat, opts.lon),
        icon: 'static/img/bus.png',
        map: GMap.map,
        title: "Linje " + opts.line
    });

    // Private method to update visible vehicle state
    function _setState(info) {
        // Set correct icon
        if(self._deviation !== info.deviation) {
            var icon = 
                'static/img/bus' + ((info.deviation === 0) ? '.png' : '_late.png');
            self._marker.setIcon(icon);
            
            // Set correct title
            var title = 
                'Linje' + info.line + 
                (info.deviation !== 0 ? ' (Avvikelse '+(info.deviation/60)+' min)' : '');
            self._marker.setTitle(title);

            // Update own value
            self._deviation = info.deviation;
        }
    }

    // This method accepts new vehicle info and updates it accordingly
    this.setPosition = function(pos) { 
        self._pos = self._to;
        self._to = pos;

        //Has coordinates been revised?
        var force = (pos.version !== self._version);
        self._version = pos.version;

        if(self._timer === false || force === true) {
            self._pos = pos;
            var newPos = new google.maps.LatLng(pos.lat, pos.lon);
            self._marker.setPosition(newPos); 
        }

        _setState(pos);

        //New tangents
        self._dx = pos.lat - self._pos.lat;
        self._dy = pos.lon - self._pos.lon;        
    };
    this.animate = function() {
        self._timer = setInterval(self.next, 200);
    };
    this.stop = function() {
        clearInterval(self._timer);
        self._timer = false;
    };
    this.next = function() {
        // Calculate new position
        self._pos.lat += self._dx*0.1; 
        self._pos.lon += self._dy*0.1;

        //Threshold XXX: really useful?
        if(Math.abs(self._pos.lat - self._to.lat) < 0.00001) {   
            self._dx = 0;
            self._pos.lat = self._to.lat;
        }
        if(Math.abs(self._pos.lon - self._to.lon) < 0.00001) {   
            self._dy = 0;
            self._pos.lon = self._to.lon;
        }

        var pos = new google.maps.LatLng(self._pos.lat, self._pos.lon);
        self._marker.setPosition(pos);
    };
    this.remove = function() {
        self.stop();
        self.hide();
    };
    this.hide = function() {
        self._marker.setMap(null);
        clearTimeout(self._timer);
    };
    this.show = function() {
        self._marker.setMap(GMap.map);
        self._timer = setInterval(self.next, 200);
    };

    _setState(opts);
}

/*
 * Traffic object
 * Fetches vehicle coordinates at a regular interval. 
 */
var Traffic = (function(){
    var _routes = [],
        _timer = false,
        _vehicles = {},
        _hideState = {};

    // Some private functions
    function _fetch() {
        Cmd.send('getVehicles', {
            callbackParameter: "callback",
            timeout: 10000,
            success: _update,
            error: function() {
                $(document).trigger("Server.error");
            }
        });
    }
    function _update(json) {
        // Reload timer
        _timer = setTimeout(_fetch, Config.pollInterval);

        var keys = {};
        //Update or create new items
        for(var i in json) {
            if(json.hasOwnProperty(i)) {
                var v = json[i];
                keys[v.id] = true; // Mark vehicle as seen
                if(v.id in _vehicles) {
                    //If coordinates has changed version, set position immediatly
                    _vehicles[v.id].setPosition(v);
                } else {
                    _vehicles[v.id] = new Vehicle(v);
                    if(Config.animate) {
                        _vehicles[v.id].animate();
                    }
                }
                
                // Check if vehicle is hidden by user
                if(v.line in _hideState) {
                    _vehicles[v.id].hide();
                }
            }
        }

        //Remove orphan items
        for(i in _vehicles) {
            if(_vehicles.hasOwnProperty(i)) {
                if(!(i in keys)) {
                    _vehicles[i].remove();
                    delete _vehicles[i];
                }
            }
        }
    }

    // Return external functions
    return {
        startTracking: function() {
            //Start tracking of vehicles
            _timer = setTimeout(_fetch, 0);
        },
        stopTracking: function() {
            clearTimeout(_timer);
            for(var i in _vehicles) {
                if(_vehicles.hasOwnProperty(i)) {
                    _vehicles[i].stop();
                }
            }
        },
        getRoutes: function() {
            //Fetch routes
            Cmd.send('getRoutes', {
                callbackParameter: "callback",
                timeout: 5000,
                success: function(json){
                    _routes = [];
                    $("#toolbar > ul").empty();
                    for(var i in json) {
                        if(json.hasOwnProperty(i)) {
                            var r = new Route(json[i]);
                            _routes.push(r);
                            json[i].route = r;
                            json[i].color = Color.get(json[i].name);
                            //XXX: Don't draw list items here
                            $("#toolbar > ul").append($("#stationItem").tmpl(json[i]));
                        }
                    }
                },
                error: function(){
                    $(document).trigger("Server.error");
                }
            });
        },
        hideLine: function(val) {
            _hideState[val] = true;
            for(var i in _vehicles) {
                if(_vehicles.hasOwnProperty(i)) {
                    var v = _vehicles[i];
                    if(v.line == val) {
                        v.hide();
                    }
                }
            }
        },
        showLine: function(val) {
            delete _hideState[val];
            for(var i in _vehicles) {
                if(_vehicles.hasOwnProperty(i)) {
                    var v = _vehicles[i];
                    if(v.line == val) {
                        v.show();
                    }
                }
            }
        }
    };
})();

/*
 * Displays error message in case of lost server connection
 */
var ErrorHandler = {
    $popup: false,
    $shade: false,
    msg: "",
    init: function() {
        // Create popup
        ErrorHandler.msg = $("#serverError").html();
        ErrorHandler.$shade = $("<div>")
            .hide()
            .attr('id', 'shade')
            .appendTo('body');
        ErrorHandler.$popup = $("<div>")
            .hide()
            .attr('id', 'errorPopup')
            .appendTo('body');
        $(document).bind("Server.error", function() {
            ErrorHandler.$popup.html(ErrorHandler.msg).show();
            ErrorHandler.$shade.show();
        });
    }
};

$(document).ready(function() {
    ErrorHandler.init();

    // Check for IE and abort if found
    var browserCheck = (function () {
        var str = navigator.userAgent;
        if(str.search("MSIE 7.0") !== -1 || str.search("MSIE 6.0") !== -1) {
            ErrorHandler.msg = $("#notSupported").html();
            $(document).trigger("Server.error");
            return false;
        }
        return true;
    })();
    //if(!browserCheck) { return; }
    
    // Create a google map
    GMap.init('#map_canvas');

    // Fetch all routes and start fetching vehicle coordinates
    Traffic.getRoutes();
    Traffic.startTracking();
    
    // Stop updates if error is encountered
    $(document).bind("Server.error", Traffic.stopTracking);

    // Show/hide lines when clicking
    $("#toolbar > ul > li > input ").live("click", function(e) {
        var item = $.tmplItem(e.target);
        var enabled = (e.target.checked);
        if(enabled) {
            item.data.route.show();
            Traffic.showLine(item.data.name);
            $(e.target).parent().removeClass('inactive');
        }
        else {
            item.data.route.hide();
            Traffic.hideLine(item.data.name);
            $(e.target).parent().addClass('inactive');
        }
    });
});