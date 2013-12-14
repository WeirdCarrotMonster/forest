function Dashboard($scope, $http, $timeout) {
    $scope.servers = [];

    $scope.getDashboardData = function() {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "status_report"
            }
        }).
        success(function(data, status, headers, config) {
            console.log(data);
        }).
        error(function(data, status, headers, config) {
          // called asynchronously if an error occurs
          // or server returns response with an error status.
        });
    };
    $scope.getDashboardData();
}