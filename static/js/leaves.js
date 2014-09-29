forest.factory("Leaves", function($resource) {
  return $resource("/api/leaves/:id/:query", null, {
    'update': {method: 'PATCH', params: {id: "@_id"}}
  });
});

forest.controller("LeavesIndex", function($scope, $routeSegment, $rootScope, Leaves) {
  Leaves.query(function(data) {
    $scope.leaves = data;
  });

  $rootScope.$on('leavesUpdateRequired', function(event, args) {
    $scope.loadLeaves();
  });

  $scope.search = "";
});

forest.controller("LeavesIndexItem", function($scope, $routeSegment, Leaves) {
  $scope.init = function(data) {
    $scope.resource = data;
  }

  $scope.leafButtonClass = function () {
    if ($scope.busy) {
      return "fa fa-refresh fa-spin";
    }else
    if ($scope.resource.active) {
      return "fa fa-check"
    }else {
      return "fa fa-times"
    }
  }

  $scope.leafButtonBgClass = function () {
    if ($scope.busy) {
      return "statusbusy";
    }else
    if ($scope.resource.active) {
      return "statuson"
    }else {
      return "statusoff"
    }
  }

  $scope.toggleLeaf = function() {
    $scope.busy = true;
    $scope.resource.active = !$scope.resource.active;
    $scope.resource.$update().then(function (a){
      $scope.busy = false;
    });
  }
});

forest.controller("LeafIndex", function($scope, $routeSegment) {
    $scope.id = $routeSegment.$routeParams.id;
});

forest.controller("LeafLogs", function($scope, $routeSegment, $http, Leaves) {
  Leaves.query({id: $scope.$parent.id, query: "logs"}, function(data) {
    $scope.logs = data;
  });
  $scope.convertDate = function (date) {
    moment.lang("ru");
    return moment(date).format('LLLL');
  };
});

forest.controller("LeafSettings", function($scope, $routeSegment, $http, $rootScope) {
    $scope.status = "saved";

    $scope.checkbox_list_helper = function (settings_list, value) {
        var idx = settings_list.indexOf(value);

        if (idx > -1){
            settings_list.splice(idx, 1);
        }
        else{
            settings_list.push(value);
        }
    }

    $scope.buttonClass = function () {
        if ($scope.status=="saved"){
            return "fa fa-save";
        }else
        if ($scope.status=="saving"){
            return "fa fa-circle-o-notch fa-spin";
        }
        if ($scope.status=="failed"){
            return "fa fa-warning";
        }
        if ($scope.status=="success"){
            return "fa fa-check";
        }
    }

    $scope.buttonText = function () {
        if ($scope.status=="saved"){
            return "Сохранить настройки";
        }else
        if ($scope.status=="saving"){
            return "Сохраняем...";
        }
        if ($scope.status=="failed"){
            return "Ошибка";
        }
        if ($scope.status=="success"){
            return "Сохранено";
        }
    }

    $scope.loadSettings = function () {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "get_leaf_settings",
                leaf_id: $scope.$parent.id
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
                if ($scope.settings.template.custom[key].type == "checkbox_list" && $scope.settings.custom[key] == undefined){
                    $scope.settings.custom[key] = Array();
                }
            }
            for (var key in $scope.settings.template.common){
                if ($scope.settings.template.common[key].type == "list" && $scope.settings.common[key] == undefined){
                    $scope.settings.common[key] = Array();
                }
                if ($scope.settings.template.common[key].type == "checkbox_list" && $scope.settings.common[key] == undefined){
                    $scope.settings.common[key] = Array();
                }
            }
        }).
        error(function(data, status, headers, config) {
        });
    }
    $scope.loadSettings();

    $scope.saveSettings = function() {
        if ($scope.status == "saving"){
            return;
        }
        $scope.status = "saving";
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "set_leaf_settings",
                leaf_id: $scope.$parent.leafid,
                settings: {
                    custom: $scope.settings.custom,
                    common: $scope.settings.common
                }
            }
        }).
        success(function(data, status, headers, config) {
            if (data["result"] == "success"){
                $rootScope.$emit('leavesUpdateRequired', {});
                $scope.status = "success";
            }
            else{
                $scope.status = "failed";
            }
        }).
        error(function(data, status, headers, config) {
            $scope.status = "failed";
        });
    }
})

function LeafAdd($scope, $routeSegment, $http, $rootScope, loader) {
    $scope.checkbox_list_helper = function (settings_list, value) {
        var idx = settings_list.indexOf(value);

        if (idx > -1){
            settings_list.splice(idx, 1);
        }
        else{
            settings_list.push(value);
        }
    }

    $scope.loadSpecies = function() {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "get_species"
            }
        }).
        success(function(data, status, headers, config) {
            if (data["result"] == "success"){
                $scope.species = data["species"];
            }
        }).
        error(function(data, status, headers, config) {
        });
    }
    $scope.loadSpecies();

    $scope.loadSettingsTemplate = function() {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "get_default_settings",
                specie_id: $scope.leaf_type
            }
        }).
        success(function(data, status, headers, config) {
            $scope.settings = {
                custom: {},
                common: {}
            };
            if (data["result"] == "success"){
                $scope.template = data["settings"];
            }
            for (var key in $scope.template.custom){
                if ($scope.template.custom[key].type == "list"){
                    $scope.settings.custom[key] = Array();
                }
                if ($scope.template.custom[key].type == "checkbox_list"){
                    $scope.settings.custom[key] = Array();
                }
            }
            for (var key in $scope.template.common){
                if ($scope.template.common[key].type == "list"){
                    $scope.settings.common[key] = Array();
                }
                if ($scope.template.common[key].type == "checkbox_list"){
                    $scope.settings.common[key] = Array();
                }
            }
        }).
        error(function(data, status, headers, config) {
        });
    }

    $scope.leaf_type = undefined;
    $scope.leaf_name = "";
    $scope.leaf_description = "";

    $scope.saveLeaf = function() {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "create_leaf",
                name: $scope.leaf_name,
                leaf_type: $scope.leaf_type,
                desc: $scope.leaf_description,
                settings: $scope.settings
            }
        }).
        success(function(data, status, headers, config) {
            if (data["result"] == "success"){
                $rootScope.$emit('leavesUpdateRequired', {});
                // window.location = '/leaves/' + $scope.leaf_name +'/logs'
            }
        }).
        error(function(data, status, headers, config) {
        });
    }
}
