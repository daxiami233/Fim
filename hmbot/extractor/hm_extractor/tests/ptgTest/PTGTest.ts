/*
 * Copyright (c) 2024 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import { SceneConfig } from '../../src/arkanalyzer/src/Config';
import { Scene } from '../../src/arkanalyzer/src/Scene';
import { ArkFile } from '../../src/arkanalyzer/src';
import { ArkMethod, CallGraph, CallGraphBuilder, DEFAULT_ARK_CLASS_NAME, MethodSignature } from '../../src/arkanalyzer/src';
import { PageTransitionGraph} from '../../src/core/model/PageTransitionGraph';
import { BasicPTGModelBuilder} from '../../src/core/model/builder/BasicPTGModelBuilder';

import { RouterEdgeBuilderwithCode } from '../../src/core/model/builder/edgeBuilder/RouterEdgeBuilderwithCode';
import { RouterEdgeBuilderwithIR} from '../../src/core/model/builder/edgeBuilder/RouterEdgeBuilderwithIR';
import { NavigationEdgeBuilderwithIR} from '../../src/core/model/builder/edgeBuilder/NavigationEdgeBuilderwithIR';

import { MainPageNodeBuilder } from '../../src/core/model/builder/nodeBuilder/NodeBuilder';
import { RouterMapNodeBuilder } from '../../src/core/model/builder/nodeBuilder/RouterMapNodeBuilder';


let config: SceneConfig = new SceneConfig()
config.buildFromJson('./tests/ptgTest/PTGTestConfig.json');
let projectScene: Scene = new Scene();
projectScene.buildBasicInfo(config);
projectScene.buildScene4HarmonyProject();
// let files: ArkFile[] = projectScene.getFiles();
// let fileNames: string[] = files.map(file => file.getFilePath()); console.log(fileNames);
// let map = projectScene.getModuleSceneMap();
// console.log(map);
let scene = projectScene.getModuleScene('entry');
console.log(scene);
let map = scene?.getModuleFilesMap();
console.log(map);

// function runScene(config: SceneConfig) {
//     let projectScene: Scene = new Scene();
//     projectScene.buildBasicInfo(config);
//     projectScene.buildScene4HarmonyProject();
//     projectScene.inferTypes();

//     let methods: ArkMethod[] = projectScene.getMethods();
//     let entryPoints:  MethodSignature[] = methods.map(method => method.getSignature());

//     let callGraph = new CallGraph(projectScene)
//     let callGraphBuilder = new CallGraphBuilder(callGraph, projectScene)
//     callGraphBuilder.buildClassHierarchyCallGraph(entryPoints, false)
//     console.log(`callGraph.getNodes().size: ${callGraph.getNodeNum()}`)

//     let ptg = new PageTransitionGraph(projectScene)
//     let ptgModelBuilder = new BasicPTGModelBuilder(projectScene, ptg, callGraph);

//     ptgModelBuilder.addNodeBuilder(new MainPageNodeBuilder(projectScene,ptg))
//     ptgModelBuilder.addNodeBuilder(new RouterMapNodeBuilder(projectScene,ptg))


//     ptgModelBuilder.addEdgeBuilder(new RouterEdgeBuilderwithCode(projectScene,ptg))
//     ptgModelBuilder.addEdgeBuilder(new RouterEdgeBuilderwithIR(projectScene,ptg))
//     ptgModelBuilder.addEdgeBuilder(new NavigationEdgeBuilderwithIR(projectScene,ptg))

//     ptgModelBuilder.build()
    
//     ptg.dumpDot("./out/ptg/PTG.dot" );
//     ptg.dumpJson("./out/ptg/PTG.json" );

// }
// runScene(config);
