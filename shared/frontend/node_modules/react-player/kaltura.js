
      var createReactPlayer = require('./lib/ReactPlayer').createReactPlayer
      var Player = require('./lib/players/Kaltura').default
      module.exports = createReactPlayer([{
        key: 'kaltura',
        canPlay: Player.canPlay,
        lazyPlayer: Player
      }])
    