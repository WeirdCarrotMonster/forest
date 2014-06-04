function Branches($scope, $routeSegment, $http, $rootScope, loader) {
    $scope.loadBranches = function () {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "get_branches"
            }
        }).
            success(function(data, status, headers, config) {
                if (data["result"] == "success"){
                    $scope.branches = data["branches"];
                }
            }).
            error(function(data, status, headers, config) {
            });
    }
    $scope.loadBranches();
}

function Branch($scope, $routeSegment, loader) {
    $scope.branchid = $routeSegment.$routeParams.branchid;
}

function BranchLogs($scope, $routeSegment, $http, loader) {
    $scope.loadLogs = function () {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "get_branch_logs",
                name: $scope.$parent.branchid
            }
        }).
            success(function(data, status, headers, config) {
                if (data["result"] == "success"){
                    $scope.logs = data["logs"];
                }
            }).
            error(function(data, status, headers, config) {
            });
    }
    $scope.loadLogs()
}