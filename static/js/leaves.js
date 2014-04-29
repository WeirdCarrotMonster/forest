function Leaves($scope, $routeSegment, $http, loader) {
    $scope.loadLeaves = function () {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "get_leaves"
            }
        }).
        success(function(data, status, headers, config) {
            if (data["result"] == "success"){
                $scope.leaves = data["leaves"];
            }
        }).
        error(function(data, status, headers, config) {
        });
    }
    $scope.loadLeaves();

    $scope.search = "";

    $scope.toggleLeaf = function(leaf) {
        if (leaf.busy != undefined && !leaf.busy){
            return 0;
        }
        leaf.busy = true;
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "toggle_leaf",
                name: leaf.name
            }
        }).
        success(function(data, status, headers, config) {
            if (data["result"] == "success"){
                $scope.leaves[$scope.leaves.indexOf(leaf)] = data["leaf"];
            }else{
                leaf.busy = false;
            }
        }).
        error(function(data, status, headers, config) {
            leaf.busy = false;
        });
    }
}

function Leaf($scope, $routeSegment, loader) {
    $scope.leafid = $routeSegment.$routeParams.leafid;
}

function LeafLogs($scope, $routeSegment, $http, loader) {
    $scope.loadLogs = function () {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "get_leaf_logs",
                name: $scope.$parent.leafid
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

    $scope.log_types = ["leaf.event", "leaf.initdb"];

    $scope.log_enabled = function(log_type) {
        return $scope.log_types.indexOf(log_type) != -1;
    }

    $scope.toggle_log_type = function(log_type) {
        if ($scope.log_types.indexOf(log_type) != -1){
            $scope.log_types.splice($scope.log_types.indexOf(log_type), 1);
        }else{
            $scope.log_types.push(log_type);
        }
    }
}

function LeafSettings($scope, $routeSegment, $http, loader) {
    $scope.loadSettings = function () {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "get_leaf_settings",
                name: $scope.$parent.leafid
            }
        }).
        success(function(data, status, headers, config) {
            if (data["result"] == "success"){
                $scope.settings = data["settings"];
            }
            for (var key in $scope.settings.template.custom){
                if ($scope.settings.template.custom[key].type == "list" && $scope.settings.custom[key] == undefined){
                    $scope.settings.custom[key] = Array();
                }
            }
        }).
        error(function(data, status, headers, config) {
        });
    }
    $scope.loadSettings();

    $scope.saveSettings = function() {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "set_leaf_settings",
                name: $scope.$parent.leafid,
                settings: $scope.settings
            }
        }).
        success(function(data, status, headers, config) {
            if (data["result"] == "success"){
                
            }
        }).
        error(function(data, status, headers, config) {
        });
    }
}