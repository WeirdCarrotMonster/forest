forest = angular.module('Forest', ['ngResource', 'ngRoute', 'ngAnimate', 'route-segment', 'view-segment']);

forest.config(function($routeSegmentProvider, $routeProvider, $locationProvider) {
    $routeSegmentProvider.options.autoLoadTemplates = true;

    $routeSegmentProvider
        .when('/', 'dashboard')
        .when('/air', 'air')
        .when('/branches', 'branches')
        .when('/branches/:branchid', 'branches.branch')
        .when('/branches/:branchid/logs', 'branches.branch.logs')
        .when('/species', 'species')
        .when('/leaves', 'leaves')
        .when('/roots', 'roots')
        .when('/fauna', 'fauna')
        .when('/leaves/add', 'leaves.add')
        .when('/leaves/:id', 'leaves.leaf')
        .when('/leaves/:id/settings', 'leaves.leaf.settings')
        .when('/leaves/:id/logs', 'leaves.leaf.logs')

        .segment('dashboard', {
            templateUrl: "/static/templates/dashboard.html",
            controller: Dashboard
        })

        .segment('leaves', {
            controller: this.LeavesIndex,
            templateUrl: '/static/templates/leaves.html'
        })

        .within()

        .segment('add', {
            controller: LeafAdd,
            templateUrl: '/static/templates/leaf-add.html'
        })

        .up()

        .within()

        .segment('leaf', {
            controller: this.LeafIndex,
            dependencies: ['id'],
            templateUrl: '/static/templates/leaf.html'
        })

        .within()

        .segment('logs', {
            controller: this.LeafLogs,
            templateUrl: '/static/templates/leaf-logs.html'
        })

        .up()

        .within()

        .segment('settings', {
            controller: this.LeafSettings,
            templateUrl: '/static/templates/leaf-settings.html'
        })

        .up()

        .up()

        .segment('branches', {
            controller: Branches,
            templateUrl: '/static/templates/branches.html'
        })

        .within()

        .segment('branch', {
            controller: Branch,
            dependencies: ['branchid'],
            templateUrl: '/static/templates/branch.html'
        })

        .within()

        .segment('logs', {
            controller: BranchLogs,
            templateUrl: '/static/templates/branch-logs.html'
        })

        .up()

        .up()

        .within()

        .segment('species', {
            controller: Species,
            templateUrl: '/static/templates/species.html'
        })

    $routeProvider.otherwise({redirectTo: '/'});
    $locationProvider.html5Mode(true);
});

forest.value('loader', {show: false});

function Dashboard($scope, $routeSegment, loader) {

    $scope.$routeSegment = $routeSegment;
    $scope.loader = loader;

    $scope.$on('routeSegmentChange', function() {
        loader.show = false;
    })
}

