function Dashboard($scope, $http, $timeout) {
    $scope.servers = [];

    $scope.getDashboardData = function() {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "dashboard_stats"
            }
        }).
        success(function(data, status, headers, config) {
            $scope.servers = data["servers"];
            console.log(data);
        }).
        error(function(data, status, headers, config) {
          // called asynchronously if an error occurs
          // or server returns response with an error status.
        });
    };
    $scope.getDashboardData();
}