forest = angular.module('Forest', ['ngRoute', 'ngAnimate', 'route-segment', 'view-segment']);

forest.config(function($routeSegmentProvider, $routeProvider) {

    // Configuring provider options

    $routeSegmentProvider.options.autoLoadTemplates = true;

    // Setting routes. This consists of two parts:
    // 1. `when` is similar to vanilla $route `when` but takes segment name instead of params hash
    // 2. traversing through segment tree to set it up

    $routeSegmentProvider

        .when('/', 'dashboard')
        .when('/air', 'air')
        .when('/branches', 'branches')
        .when('/leaves', 'leaves')
        .when('/roots', 'roots')
        .when('/fauna', 'fauna')
        .when('/leaves/:leafid', 'leaves.leaf')
        .when('/leaves/:leafid/settings', 'leaves.leaf.settings')
        .when('/leaves/:leafid/logs', 'leaves.leaf.logs')

        .segment('dashboard', {
            templateUrl: "/static/templates/dashboard.html",
            controller: Dashboard
        })

        .segment('leaves', {
            controller: Leaves,
            templateUrl: '/static/templates/leaves.html'
        })

        .within()

        .segment('leaf', {
            controller: Leaf,
            dependencies: ['leafid'],
            templateUrl: '/static/templates/leaf.html'
        })

        .within()

        .segment('logs', {
            controller: LeafLogs,
            templateUrl: '/static/templates/leaf-logs.html'
        })

        .up()

        .within()

        .segment('settings', {
            controller: LeafSettings,
            templateUrl: '/static/templates/leaf-settings.html'
        })

    $routeProvider.otherwise({redirectTo: '/'});
}) ;

forest.value('loader', {show: false});

function Dashboard($scope, $routeSegment, loader) {

    $scope.$routeSegment = $routeSegment;
    $scope.loader = loader;

    $scope.$on('routeSegmentChange', function() {
        loader.show = false;
    })
}