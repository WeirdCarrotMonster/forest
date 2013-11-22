function Connection($scope, $http, $timeout) {
    $scope.logs = [];
    $scope.known_functions = [];
    $scope.function = {};
    $scope.authenticated = false;
    $scope.ws_connected = false;
    $scope.width = 0;
    $scope.height = 0;
    $scope.atStart = true;

    $scope.sidebarClass = function() {
        if ($scope.atStart){
            return "sidebar-notready-start";
        }
        else if ($scope.authenticated){
            return "sidebar-ready";
        }
        else{
            return "sidebar-notready";
        }
    }

    $scope.contentClass = function() {
        if ($scope.atStart){
            return "content-full-start";
        }
        else if ($scope.authenticated){
            return "content-with-sidebar";
        }
        else{
            return "content-full";
        }
    }

    $scope.websocketClass = function() {
        if ($scope.ws_connected){
            return "websocket-connected";
        }
        else {
            return "websocket-disconnected";
        }
    }
    $scope.websocketText = function() {
        if ($scope.ws_connected){
            return "Сокет подключен";
        }
        else {
            return "Нет соединения с сервером";
        }
    }

    $scope.loginUser = function() {
        var username = $("#username").val();
        var password = $("#password").val();
        var data = {
            "function": "login_user",
            "username": username,
            "password": password
        };
        $http({
            method: 'POST',
            url: "/",
            data: JSON.stringify(data)
        }).
        success(function(data, status) {
            if (data["result"] == "success"){
                $scope.atStart = false;
                $scope.authenticated = true;
                $scope.setSocket();
            }
        }).
        error(function(data, status) {
        });
    };
    $scope.loginUser();

    $scope.setSocket = function() {
        $scope.ws_connected = false;
        $scope.webSocket = new WebSocket('ws://127.0.0.1:1234/websocket');
        $scope.webSocket.onopen = function(event) {
            $scope.ws_connected = true;
            $scope.webSocket.send('{"function": "known_functions"}');
            $scope.$apply();
        };
        $scope.webSocket.onmessage = function(event) {
            var data = JSON.parse(event.data);
            if (data["result"] == "functions")
            {
                $scope.known_functions = data["functions"];
            }
            else
            {
                $scope.logs.push(data);
            }
            $scope.$apply();
        };
        $scope.webSocket.onclose = function(event) {
            $scope.ws_connected = false;
            $scope.$apply();
            $timeout($scope.reconnectSocket,5000);
        };
    };

    $scope.reconnectSocket = function() {
        if ($scope.ws_connected == false){
            $scope.setSocket();
            $timeout($scope.reconnectSocket,2000);
        }
    };

    $scope.sendMessage = function() {
        $scope.logs = [];
        var fdata = {
            "function": $scope.function.name
        };
        $(".one_arg").each(function(){
           fdata[$(this).attr("data-arg")] = $(this).find(".input").val()
        });
        console.log(JSON.stringify(fdata));
        $scope.webSocket.send(JSON.stringify(fdata));
        $scope.messageText = "";
    };
}

function tellAngular() {
    var domElt = document.getElementById('loginForm');
    scope = angular.element(domElt).scope();
    scope.$apply(function() {
        scope.width = window.innerWidth;
        scope.height = window.innerHeight;
    });
}

document.addEventListener("DOMContentLoaded", tellAngular, false);

window.onresize = tellAngular;