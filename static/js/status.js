function Status($scope, $http) {
    $scope.servers = [];

    $scope.getStatusData = function() {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "forest_status"
            }
        }).
        success(function(data, status, headers, config) {
            $scope.servers = data["servers"];
            console.log(data);
        }).
        error(function(data, status, headers, config) {
        });
    };
    $scope.getStatusData()
};