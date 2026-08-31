let pendingCommandTasks = [];

// Make sure the blueprints exist before running the command, to avoid errors
// do "/sablebp save ~ ~ ~ 10 <ship1/ship2/ship3>" while standing in the ship
const SHIPS = [
    'ship1',
    'ship2',
    'ship3'
];

// Ship size config, replace with the values of the ship
const SHIP_HEIGHT         = 14;
// how high the deck is from the bottom of the ship
const BLOCKS_ABOVE_BOTTOM = 3;

// Random location config
const SPAWN_Y             = 150;
const AREA_SIZE           = 15000;

ServerEvents.commandRegistry(event => {
    const { commands: Commands } = event;

    event.register(
        Commands.literal('randomspawn')
            .requires(src => src.hasPermission(2))
            .executes(ctx => {
                const player = ctx.source.player;
                if (!player) {
                    ctx.source.sendFailure(
                        Component.red('This command must be run by a player!')
                    );
                    return 0;
                }

                const server = ctx.source.server;

                const randomShipIndex = Math.floor(Math.random() * SHIPS.length);
                const selectedShip = SHIPS[randomShipIndex];

                const halfArea = AREA_SIZE / 2;
                const x = Math.floor(Math.random() * AREA_SIZE) - halfArea;
                const z = Math.floor(Math.random() * AREA_SIZE) - halfArea;

                const shipBottomY = Math.floor(SPAWN_Y - SHIP_HEIGHT / 2);
                const playerY     = shipBottomY + BLOCKS_ABOVE_BOTTOM;

                server.runCommandSilent(
                    'tp ' + player.username + ' ' + x + ' ' + SPAWN_Y + ' ' + z
                );

                pendingCommandTasks.push({
                    runAtTick: server.tickCount + 10,
                    phase: 1, 
                    playerUsername: player.username,
                    chosenShip: selectedShip,
                    targetX: x,
                    targetY: playerY,
                    targetZ: z
                });

                return 1;
            })
    );
});

ServerEvents.tick(event => {
    if (pendingCommandTasks.length === 0) return;

    const currentServerTick = event.server.tickCount;

    pendingCommandTasks = pendingCommandTasks.filter(task => {
        if (currentServerTick >= task.runAtTick) {
            let targetPlayer = event.server.getPlayerList().getPlayerByName(task.playerUsername);
            
            if (targetPlayer) {
                if (task.phase === 1) {
                    
                    event.server.runCommandSilent(
                        'execute at ' + task.playerUsername +
                        ' run sablebp load ' + task.chosenShip
                    );
                    task.runAtTick = currentServerTick + 10;
                    task.phase = 2;
                    return true; 
                } 
                
                if (task.phase === 2) {
                    
                    event.server.runCommandSilent(
                        'tp ' + task.playerUsername + ' ' +
                        task.targetX + ' ' + task.targetY + ' ' + task.targetZ
                    );
                    
                    event.server.runCommandSilent(
                        'title ' + task.playerUsername + ' actionbar ' +
                        '{"text":"Spawned ' + task.chosenShip +
                        ' at [' + task.targetX + ' ~ ' + task.targetZ +
                        ']","color":"green"}'
                    );

                    return false; 
                }
            }
            return false; 
        }
        return true; 
    });
});