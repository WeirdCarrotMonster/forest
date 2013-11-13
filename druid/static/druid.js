function Connection($scope) {
  $scope.logs = [
  ];
  
  $scope.ws_connected = true;

  $scope.webSocket = new WebSocket('ws://127.0.0.1:1234/websocket');
  $scope.webSocket.onopen = function(event) {
    $scope.ws_connected = true;
    $scope.$apply();
  };
  $scope.webSocket.onmessage = function(event) {
    var data = JSON.parse(event.data);
    $scope.logs.push(data);
    $scope.$apply();
  };
  $scope.webSocket.onclose = function(event) {
    $scope.ws_connected = false;
    $scope.$apply();
  };

  $scope.sendMessage = function() {
    $scope.logs = [];
    console.log($scope.messageText);
    $scope.webSocket.send($scope.messageText);
    $scope.messageText = "";
  };
}