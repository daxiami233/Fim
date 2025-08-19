import { Scene } from "../../../arkanalyzer/src/Scene";
import { PageTransitionGraph, PTGNode } from "../PageTransitionGraph";
import { CallGraph } from "../../../arkanalyzer/src/callgraph/model/CallGraph";
import { ArkMethod } from "../../../arkanalyzer/src/core/model/ArkMethod";
import { CALLBACK_METHOD_NAME, MethodSignature, ViewTreeNode } from "../../../arkanalyzer/src";
import { NodeBuilderInterface } from "./nodeBuilder/BasicNodeBuilder";
import { NodeBuilder } from "./nodeBuilder/NodeBuilder";
import { EdgeBuilderInterface } from "./edgeBuilder/BasicEdgeBuilder";
import { RouterEdgeBuilderwithCode } from "./edgeBuilder/RouterEdgeBuilderwithCode";
import { RouterEdgeBuilderwithIR } from "./edgeBuilder/RouterEdgeBuilderwithIR";

export class BasicPTGModelBuilder {
    ptg: PageTransitionGraph;
    scene: Scene;
    cg: CallGraph;
    nodeBuilders: NodeBuilderInterface[] = [];
    edgeBuilders: EdgeBuilderInterface[] = [];


    constructor( s: Scene, p: PageTransitionGraph,c: CallGraph) {
        this.ptg = p;
        this.scene = s;
        this.cg = c;

    }
    addNodeBuilder(nodeBuilder: NodeBuilderInterface) {
        this.nodeBuilders.push(nodeBuilder);
    }
    
    addEdgeBuilder(edgeBuilder: EdgeBuilderInterface) {
        this.edgeBuilders.push(edgeBuilder);
    }

    build(){
        this.identifyPageNodes();
        this.buildBasicPTG();
    }
    
  /**
     * identify page nodes
     * @Override
        */
    public identifyPageNodes(){
        if(this.nodeBuilders.length == 0){
            this.nodeBuilders.push(new NodeBuilder(this.scene,this.ptg));
        }
        for(const nodeBuilder of this.nodeBuilders){
            nodeBuilder.identifyPageNodes();
        }
        for (const node of this.ptg.getPTGNodes()) {
            console.log(node.getPageAlias());
        }
    }

    /**
     * detect page transition in the UI listener method
     * @Override
     * @param method 
     */
    public identifyPTGEdge(ptgNode: PTGNode, method: ArkMethod) {
        if(this.nodeBuilders.length == 0){
            this.edgeBuilders.push(new RouterEdgeBuilderwithIR(this.scene,this.ptg));
        }
        for(const edgeBuilder of this.edgeBuilders){
            edgeBuilder.identifyPTGEdge(ptgNode, method);
        }
    }



    /**
     * build basic PTG
     * @Override
     */
    // 构建基本PTG
    public buildBasicPTG() {
        // 遍历PTG节点
        for(const ptgNode of this.ptg.getPTGNodes()){
            // 获取页面的视图树根节点
            // console.log("build basic PTG for " + ptgNode.getPageName());
            // 如果根节点存在，则遍历视图树
            const root = ptgNode.getViewTreeOfPage()?.getRoot();
            if(root)
                this.walkViewTree(ptgNode, root, []);
        }
    }

    /**
     * walk view tree to find the call back methods and handle them
     * @param node 
     * @returns 
     */
    public walkViewTree(ptgNode: PTGNode, node: ViewTreeNode, nodeHistory:ViewTreeNode[]) {
        if(nodeHistory.includes(node)) return;
        nodeHistory.push(node);
        if(node == undefined ) return;
        for(const operation of CALLBACK_METHOD_NAME){
            if(node.attributes.has(operation)){
                let method = this.getUICallbackMethod(ptgNode, operation, node);
                if(method!=undefined){
                    this.identifyPTGEdge(ptgNode, method);
                }
            }
        }
        
        if ( node.children.length > 0) {
            for(const child of node.children){
                this.walkViewTree(ptgNode, child, nodeHistory);
            }
        }
    } 

    /**
     * for a ViewTreeNode, get the UI callback method, which may be a page transition method
     * @param ptgNode 
     * @param op 
     * @param node 
     */
    public getUICallbackMethod(ptgNode: PTGNode, op: string, node: ViewTreeNode):ArkMethod | undefined {
        const methodSignatures = node.attributes.get(op)![1];
        for(const methodSignature of methodSignatures){
            if(methodSignature instanceof MethodSignature){
                let method = this.scene.getMethod(methodSignature);
                if(method && method.getBody()?.getCfg()){
                    return method;
                }
            }
        }
    }


}
