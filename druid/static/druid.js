function Connection($scope, $http) {
    $scope.logs = [];
    $scope.known_functions = [];
    $scope.function = {};

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

    $scope.functionChanged = function() {
        console.log("fc")
    };
}