angular.module('forest', ['n3-charts.linechart'])
.controller("Dashboard", function ($scope, $http) {

    $scope.servers = [];
    $scope.data = [];

      $scope.options =
      {
          series: [],
          lineMode: 'linear'
      };

    $scope.getNiceLookingPercent = function(part, all){
        if (all == 0){
            all = 100;
        }
        return ((part/all)*100).toFixed(0);
    };

    $scope.getLoadClass = function(part, all){
        if (all == 0){
            all = 100;
        }
        if ((part/all)*100 > 75){
            return "red";
        }
        else{
            return "green"
        }
    };

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

    $scope.getLogsData = function() {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "get_memory_logs"
            }
        }).
        success(function(data, status, headers, config) {
            var values = data["values"];
            $scope.data = [];

            var x = 0;
            for (var i = 0; i < values.length; i++){
                var one_data = {"": ""};
                for (var key in values[i]) {
                    one_data["x"] = x;
                    one_data[key] = values[i][key];
                }
                x++;
                $scope.data.push(one_data);
            }

            var keys = data["keys"];
            var series = [];
            keys.forEach(function(entry) {
                series.push({
                    "y": entry,
                    "label": entry
                })
            });
            $scope.options["series"] = series;
        }).
        error(function(data, status, headers, config) {
          // called asynchronously if an error occurs
          // or server returns response with an error status.
        });
    };
    $scope.getLogsData();
});