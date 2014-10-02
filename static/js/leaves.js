forest.controller("LeavesIndex", function($scope, $routeSegment, $rootScope, Leaves) {
  Leaves.query(function(data) {
    $scope.leaves = data;
  });

  $rootScope.$on('leavesUpdateRequired', function(event, args) {
    Leaves.query(function(data) {
        $scope.leaves = data;
    });
  });

  $scope.search = "";
});

forest.controller("LeavesIndexItem", function($scope, $routeSegment, Leaves) {
  $scope.init = function(data) {
    $scope.resource = data;
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

forest.filter('reverse', function() {
  return function(items) {
    return items.slice().reverse();
  };
});

forest.controller("LeafLogs", function($scope, Leaves) {
  Leaves.query({id: $scope.$parent.id, query: "logs"}, function(data) {
    $scope.logs = data;
  });

  $scope.convertDate = function (date) {
    moment.lang("ru");
    return moment(date).format('LLLL');
  };

  $scope.updateLogs = function() {
      var begin = $scope.logs[0]._id;
      Leaves.query({id: $scope.$parent.id, query: "logs", from: begin}, function(data) {
        var logs = data;
        var logs_new = []
        for (var i=logs.length - 1; i >= 0; i--){
          logs_new.push(logs[i])
        }
        for (var i=0; i < $scope.logs.length; i++){
          logs_new.push($scope.logs[i])
        }
        $scope.logs = logs_new;
      });
  };
});

forest.controller("LeafSettings", function($scope, $rootScope, Leaves) {
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

  Leaves.get({id: $scope.$parent.id, query: "settings"}, function(data) {
    $scope.settings = data

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
  });

  $scope.saveSettings = function() {
    if ($scope.status == "saving"){
        return;
    }
    $scope.status = "saving";

    $scope.settings.$save({id: $scope.$parent.id, query: "settings"}).then(function(a){
      $rootScope.$emit('leavesUpdateRequired', {});
      $scope.status = "success";
    });
  }
})

forest.controller("LeafAdd", function($scope, $rootScope, Leaves, Species) {
    $scope.checkbox_list_helper = function (settings_list, value) {
        var idx = settings_list.indexOf(value);

        if (idx > -1){
            settings_list.splice(idx, 1);
        }
        else{
            settings_list.push(value);
        }
    }

    $scope.template = {};
    $scope.settings = {};
    $scope.settings.common = {};
    $scope.leaf_type = undefined;
    $scope.leaf_name = "";
    $scope.leaf_description = "";


    Species.query(function(data) {
        $scope.species = data;
    });

    Leaves.get({query: "settings"}, function(data) {
        $scope.template.common = data;

        for (var key in $scope.template.common){
            if ($scope.template.common[key].type == "list"){
                $scope.settings.common[key] = Array();
            }
            if ($scope.template.common[key].type == "checkbox_list"){
                $scope.settings.common[key] = Array();
            }
        }
    });

    $scope.loadSettingsTemplate = function() {
        $scope.template.custom = $scope.leaf_type.settings;

        $scope.settings.custom = {};
        for (var key in $scope.template.custom){
            if ($scope.template.custom[key].type == "list"){
                $scope.settings.custom[key] = Array();
            }
            if ($scope.template.custom[key].type == "checkbox_list"){
                $scope.settings.custom[key] = Array();
            }
        }
    }

    $scope.saveLeaf = function() {
        var leaf = Leaves.save({
            name: $scope.leaf_name,
            leaf_type: $scope.leaf_type._id,
            desc: $scope.leaf_description,
            settings: $scope.settings
        })

        console.log(leaf);
    }
});
